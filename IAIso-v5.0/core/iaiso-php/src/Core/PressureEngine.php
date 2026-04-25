<?php

declare(strict_types=1);

namespace IAIso\Core;

use IAIso\Audit\Event;
use IAIso\Audit\NullSink;
use IAIso\Audit\Sink;

/**
 * The IAIso pressure engine. Tracks accumulated load, decays over time,
 * and emits lifecycle events on threshold crossings.
 *
 * <p>See {@code spec/pressure/README.md} for normative semantics.
 *
 * <p>Wire-format events emitted: {@code engine.init}, {@code engine.step},
 * {@code engine.step.rejected}, {@code engine.escalation},
 * {@code engine.release}, {@code engine.locked}, {@code engine.reset}.
 */
final class PressureEngine
{
    private readonly PressureConfig $cfg;
    private readonly string $executionId;
    private readonly Sink $audit;
    private readonly Clock $clock;
    private readonly Clock $timestampClock;

    // mutable state
    private float $pressure = 0.0;
    private int $stepCount = 0;
    private Lifecycle $lifecycle = Lifecycle::Init;
    private float $lastStepAt = 0.0;

    public function __construct(PressureConfig $cfg, EngineOptions $opts)
    {
        $cfg->validate();
        $this->cfg = $cfg;
        $this->executionId = $opts->executionId !== ''
            ? $opts->executionId
            : 'exec-' . bin2hex(random_bytes(6));
        $this->audit = $opts->auditSink ?? NullSink::instance();
        $this->clock = $opts->clock ?? WallClock::instance();
        $this->timestampClock = $opts->timestampClock ?? $this->clock;
        $this->lastStepAt = $this->clock->now();
        $this->emit('engine.init', ['pressure' => 0.0]);
    }

    public function getConfig(): PressureConfig { return $this->cfg; }
    public function getExecutionId(): string    { return $this->executionId; }
    public function getPressure(): float        { return $this->pressure; }
    public function getLifecycle(): Lifecycle   { return $this->lifecycle; }

    public function snapshot(): PressureSnapshot
    {
        return new PressureSnapshot($this->pressure, $this->stepCount, $this->lifecycle, $this->lastStepAt);
    }

    /** Account for a unit of work; advance the engine. */
    public function step(StepInput $work): StepOutcome
    {
        if ($this->lifecycle === Lifecycle::Locked) {
            $this->emit('engine.step.rejected', [
                'reason'           => 'locked',
                'requested_tokens' => $work->tokens,
                'requested_tools'  => $work->toolCalls,
            ]);
            return StepOutcome::Locked;
        }

        $now = $this->clock->now();
        $elapsed = max(0.0, $now - $this->lastStepAt);

        $delta = ($work->tokens / 1000.0) * $this->cfg->tokenCoefficient
            + $work->toolCalls * $this->cfg->toolCoefficient
            + $work->depth * $this->cfg->depthCoefficient;
        $decay = $this->cfg->dissipationPerStep + $elapsed * $this->cfg->dissipationPerSecond;

        $this->pressure = self::clamp01($this->pressure + $delta - $decay);
        $this->stepCount += 1;
        $this->lastStepAt = $now;
        $this->lifecycle = Lifecycle::Running;

        $this->emit('engine.step', [
            'step'       => $this->stepCount,
            'pressure'   => $this->pressure,
            'delta'      => $delta,
            'decay'      => $decay,
            'tokens'     => $work->tokens,
            'tool_calls' => $work->toolCalls,
            'depth'      => $work->depth,
            'tag'        => $work->tag,
        ]);

        $pressure = $this->pressure;
        if ($pressure >= $this->cfg->releaseThreshold) {
            $this->emit('engine.release', [
                'pressure'  => $pressure,
                'threshold' => $this->cfg->releaseThreshold,
            ]);
            $this->pressure = 0.0;
            if ($this->cfg->postReleaseLock) {
                $this->lifecycle = Lifecycle::Locked;
                $this->emit('engine.locked', ['reason' => 'post_release_lock']);
            } else {
                $this->lifecycle = Lifecycle::Running;
            }
            return StepOutcome::Released;
        }
        if ($pressure >= $this->cfg->escalationThreshold) {
            $this->lifecycle = Lifecycle::Escalated;
            $this->emit('engine.escalation', [
                'pressure'  => $pressure,
                'threshold' => $this->cfg->escalationThreshold,
            ]);
            return StepOutcome::Escalated;
        }
        return StepOutcome::Ok;
    }

    /** Reset the engine. Emits {@code engine.reset}. */
    public function reset(): PressureSnapshot
    {
        $this->pressure = 0.0;
        $this->stepCount = 0;
        $this->lastStepAt = $this->clock->now();
        $this->lifecycle = Lifecycle::Init;
        $this->emit('engine.reset', ['pressure' => 0.0]);
        return $this->snapshot();
    }

    private function emit(string $kind, array $data): void
    {
        $this->audit->emit(new Event(
            $this->executionId,
            $kind,
            $this->timestampClock->now(),
            $data,
        ));
    }

    private static function clamp01(float $v): float
    {
        if ($v < 0.0) return 0.0;
        if ($v > 1.0) return 1.0;
        return $v;
    }
}
