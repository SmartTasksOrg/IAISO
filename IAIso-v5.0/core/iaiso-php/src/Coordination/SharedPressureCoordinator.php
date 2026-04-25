<?php

declare(strict_types=1);

namespace IAIso\Coordination;

use IAIso\Audit\Event;
use IAIso\Audit\NullSink;
use IAIso\Audit\Sink;
use IAIso\Core\Clock;
use IAIso\Core\WallClock;
use IAIso\Policy\Aggregator;
use IAIso\Policy\SumAggregator;

/**
 * In-memory coordinator that aggregates pressure across a single
 * process's executions.
 */
class SharedPressureCoordinator
{
    /** @var array<string,float> */
    private array $pressures = [];
    private CoordinatorLifecycle $lifecycle = CoordinatorLifecycle::Nominal;
    private float $lastNotifyAt = 0.0;
    protected readonly Clock $clock;
    private readonly Sink $auditSink;

    /**
     * @param (callable(Snapshot):void)|null $onEscalation
     * @param (callable(Snapshot):void)|null $onRelease
     */
    public function __construct(
        protected readonly string $coordinatorId,
        protected readonly float $escalationThreshold,
        protected readonly float $releaseThreshold,
        protected readonly float $notifyCooldownSeconds,
        protected readonly Aggregator $aggregator,
        ?Sink $auditSink,
        protected $onEscalation,
        protected $onRelease,
        ?Clock $clock,
        bool $emitInit = true,
    ) {
        if ($releaseThreshold <= $escalationThreshold) {
            throw new CoordinatorException(
                "release_threshold must exceed escalation_threshold ($releaseThreshold <= $escalationThreshold)");
        }
        $this->auditSink = $auditSink ?? NullSink::instance();
        $this->clock = $clock ?? WallClock::instance();
        if ($emitInit) {
            $this->emit('coordinator.init', [
                'coordinator_id' => $coordinatorId,
                'aggregator'     => $aggregator->name(),
                'backend'        => 'memory',
            ]);
        }
    }

    public static function builder(): SharedPressureCoordinatorBuilder
    {
        return new SharedPressureCoordinatorBuilder();
    }

    public function getCoordinatorId(): string { return $this->coordinatorId; }
    public function getAggregator(): Aggregator { return $this->aggregator; }

    public function register(string $executionId): Snapshot
    {
        $this->pressures[$executionId] = 0.0;
        $this->emit('coordinator.execution_registered', ['execution_id' => $executionId]);
        return $this->snapshot();
    }

    public function unregister(string $executionId): Snapshot
    {
        unset($this->pressures[$executionId]);
        $this->emit('coordinator.execution_unregistered', ['execution_id' => $executionId]);
        return $this->snapshot();
    }

    public function update(string $executionId, float $pressure): Snapshot
    {
        if ($pressure < 0.0 || $pressure > 1.0) {
            throw new CoordinatorException("pressure must be in [0, 1], got $pressure");
        }
        $this->pressures[$executionId] = $pressure;
        return $this->evaluate();
    }

    public function reset(): int
    {
        $count = count($this->pressures);
        foreach ($this->pressures as $k => $_) {
            $this->pressures[$k] = 0.0;
        }
        $this->lifecycle = CoordinatorLifecycle::Nominal;
        $this->emit('coordinator.reset', ['fleet_size' => $count]);
        return $count;
    }

    public function snapshot(): Snapshot
    {
        $agg = $this->aggregator->aggregate($this->pressures);
        ksort($this->pressures, SORT_STRING);
        return new Snapshot(
            $this->coordinatorId, $agg, $this->lifecycle,
            count($this->pressures), $this->pressures,
        );
    }

    /** Replace per-execution pressures wholesale. Used by Redis variant. */
    protected function setPressuresFromMap(array $updated): void
    {
        $this->pressures = [];
        foreach ($updated as $k => $v) {
            $this->pressures[(string) $k] = (float) $v;
        }
    }

    protected function evaluate(): Snapshot
    {
        $now = $this->clock->now();
        $agg = $this->aggregator->aggregate($this->pressures);
        $prior = $this->lifecycle;
        $inCooldown = ($now - $this->lastNotifyAt) < $this->notifyCooldownSeconds;

        if ($agg >= $this->releaseThreshold) {
            $next = CoordinatorLifecycle::Released;
        } elseif ($agg >= $this->escalationThreshold) {
            $next = $prior === CoordinatorLifecycle::Nominal
                ? CoordinatorLifecycle::Escalated : $prior;
        } else {
            $next = CoordinatorLifecycle::Nominal;
        }
        $this->lifecycle = $next;

        if ($next !== $prior && !$inCooldown) {
            $this->lastNotifyAt = $now;
            switch ($next) {
                case CoordinatorLifecycle::Released:
                    $this->emit('coordinator.release', [
                        'aggregate_pressure' => $agg,
                        'threshold' => $this->releaseThreshold,
                    ]);
                    if ($this->onRelease !== null) {
                        ($this->onRelease)($this->snapshot());
                    }
                    break;
                case CoordinatorLifecycle::Escalated:
                    $this->emit('coordinator.escalation', [
                        'aggregate_pressure' => $agg,
                        'threshold' => $this->escalationThreshold,
                    ]);
                    if ($this->onEscalation !== null) {
                        ($this->onEscalation)($this->snapshot());
                    }
                    break;
                case CoordinatorLifecycle::Nominal:
                    $this->emit('coordinator.returned_to_nominal', [
                        'aggregate_pressure' => $agg,
                    ]);
                    break;
            }
        }
        return $this->snapshot();
    }

    protected function emit(string $kind, array $data): void
    {
        $this->auditSink->emit(new Event(
            'coord:' . $this->coordinatorId, $kind, $this->clock->now(), $data,
        ));
    }
}
