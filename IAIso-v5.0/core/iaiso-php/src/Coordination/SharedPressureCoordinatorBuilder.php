<?php

declare(strict_types=1);

namespace IAIso\Coordination;

use IAIso\Audit\Sink;
use IAIso\Core\Clock;
use IAIso\Policy\Aggregator;
use IAIso\Policy\SumAggregator;

/** Builder for {@see SharedPressureCoordinator}. */
final class SharedPressureCoordinatorBuilder
{
    private string $coordinatorId = 'default';
    private float $escalationThreshold = 5.0;
    private float $releaseThreshold = 8.0;
    private float $notifyCooldownSeconds = 1.0;
    private Aggregator $aggregator;
    private ?Sink $auditSink = null;
    /** @var (callable(Snapshot):void)|null */
    private $onEscalation = null;
    /** @var (callable(Snapshot):void)|null */
    private $onRelease = null;
    private ?Clock $clock = null;

    public function __construct()
    {
        $this->aggregator = new SumAggregator();
    }

    public function coordinatorId(string $v): self          { $this->coordinatorId = $v; return $this; }
    public function escalationThreshold(float $v): self     { $this->escalationThreshold = $v; return $this; }
    public function releaseThreshold(float $v): self        { $this->releaseThreshold = $v; return $this; }
    public function notifyCooldownSeconds(float $v): self   { $this->notifyCooldownSeconds = $v; return $this; }
    public function aggregator(Aggregator $a): self         { $this->aggregator = $a; return $this; }
    public function auditSink(?Sink $s): self               { $this->auditSink = $s; return $this; }
    public function clock(?Clock $c): self                  { $this->clock = $c; return $this; }

    /** @param callable(Snapshot):void $cb */
    public function onEscalation(callable $cb): self        { $this->onEscalation = $cb; return $this; }

    /** @param callable(Snapshot):void $cb */
    public function onRelease(callable $cb): self           { $this->onRelease = $cb; return $this; }

    public function build(): SharedPressureCoordinator
    {
        return new SharedPressureCoordinator(
            $this->coordinatorId, $this->escalationThreshold, $this->releaseThreshold,
            $this->notifyCooldownSeconds, $this->aggregator, $this->auditSink,
            $this->onEscalation, $this->onRelease, $this->clock, true,
        );
    }
}
