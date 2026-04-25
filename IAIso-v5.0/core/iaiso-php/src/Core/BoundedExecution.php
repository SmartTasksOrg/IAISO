<?php

declare(strict_types=1);

namespace IAIso\Core;

use IAIso\Audit\Event;
use IAIso\Audit\NullSink;
use IAIso\Audit\Sink;

/**
 * High-level execution facade. Composes a {@see PressureEngine} with
 * an audit sink and lifecycle management.
 *
 * <p>Use {@see BoundedExecution::run()} for the closure style with
 * automatic cleanup, or {@see BoundedExecution::start()} + manual
 * {@see BoundedExecution::close()} for explicit lifecycle control.
 */
final class BoundedExecution
{
    private readonly PressureEngine $engine;
    private readonly Sink $auditSink;
    private readonly Clock $timestampClock;
    private bool $closed = false;

    private function __construct(BoundedExecutionOptions $opts)
    {
        $execId = $opts->executionId !== null && $opts->executionId !== ''
            ? $opts->executionId
            : 'exec-' . bin2hex(random_bytes(6));
        $cfg = $opts->config ?? PressureConfig::defaults();
        $clock = $opts->clock ?? WallClock::instance();
        $tsClock = $opts->timestampClock ?? $clock;
        $this->auditSink = $opts->auditSink ?? NullSink::instance();
        $this->timestampClock = $tsClock;
        $this->engine = new PressureEngine($cfg,
            new EngineOptions($execId, $this->auditSink, $clock, $tsClock));
    }

    /** Construct a {@see BoundedExecution}. The caller MUST {@see close()} it. */
    public static function start(BoundedExecutionOptions $opts): self
    {
        return new self($opts);
    }

    /**
     * Run a closure inside a bounded execution; closes on exit.
     *
     * @param callable(self):void $body
     */
    public static function run(BoundedExecutionOptions $opts, callable $body): void
    {
        $exec = self::start($opts);
        $errored = false;
        try {
            $body($exec);
        } catch (\Throwable $e) {
            $errored = true;
            throw $e;
        } finally {
            $exec->closeWith($errored);
        }
    }

    public function getEngine(): PressureEngine     { return $this->engine; }
    public function snapshot(): PressureSnapshot    { return $this->engine->snapshot(); }

    /** Account for tokens with an optional tag. */
    public function recordTokens(int $tokens, ?string $tag = null): StepOutcome
    {
        return $this->engine->step(new StepInput(tokens: $tokens, tag: $tag));
    }

    /** Account for a single tool invocation. */
    public function recordToolCall(string $name, int $tokens = 0): StepOutcome
    {
        return $this->engine->step(new StepInput(tokens: $tokens, toolCalls: 1, tag: $name));
    }

    /** General step accounting. */
    public function recordStep(StepInput $work): StepOutcome
    {
        return $this->engine->step($work);
    }

    /** Pre-check the engine state without advancing it. */
    public function check(): StepOutcome
    {
        return match ($this->engine->getLifecycle()) {
            Lifecycle::Locked    => StepOutcome::Locked,
            Lifecycle::Escalated => StepOutcome::Escalated,
            default              => StepOutcome::Ok,
        };
    }

    public function reset(): PressureSnapshot
    {
        return $this->engine->reset();
    }

    /** Close the execution, emitting {@code execution.closed}. Idempotent. */
    public function close(): void
    {
        $this->closeWith(false);
    }

    private function closeWith(bool $errored): void
    {
        if ($this->closed) return;
        $this->closed = true;
        $snap = $this->engine->snapshot();
        $this->auditSink->emit(new Event(
            $this->engine->getExecutionId(),
            'execution.closed',
            $this->timestampClock->now(),
            [
                'final_pressure'  => $snap->pressure,
                'final_lifecycle' => $snap->lifecycle->value,
                'exception'       => $errored ? 'error' : null,
            ],
        ));
    }

    public function __destruct()
    {
        // Defensive: PHP's GC will fire this if the user forgets to close().
        $this->closeWith(false);
    }
}
