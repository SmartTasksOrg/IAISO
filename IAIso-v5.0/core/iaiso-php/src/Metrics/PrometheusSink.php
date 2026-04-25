<?php

declare(strict_types=1);

namespace IAIso\Metrics;

use IAIso\Audit\Event;
use IAIso\Audit\Sink;

/**
 * IAIso Prometheus metrics sink.
 *
 * <p>Structurally typed — this module doesn't depend on any specific
 * Prometheus client library. The official {@code promphp/prometheus_client_php}
 * library satisfies these interfaces with thin adapters.
 *
 * <p>Suggested histogram buckets for {@code iaiso_step_delta}:
 * see {@see SUGGESTED_HISTOGRAM_BUCKETS}.
 */
final class PrometheusSink implements Sink
{
    /** Suggested histogram buckets for {@code iaiso_step_delta}. */
    public const SUGGESTED_HISTOGRAM_BUCKETS =
        [0.0, 0.01, 0.03, 0.05, 0.1, 0.2, 0.5, 1.0];

    public function __construct(
        private readonly ?CounterVec $events = null,
        private readonly ?Counter $escalations = null,
        private readonly ?Counter $releases = null,
        private readonly ?GaugeVec $pressure = null,
        private readonly ?Histogram $stepDelta = null,
    ) {
    }

    public function emit(Event $event): void
    {
        $this->events?->labels($event->kind)->inc();
        switch ($event->kind) {
            case 'engine.escalation':
                $this->escalations?->inc();
                break;
            case 'engine.release':
                $this->releases?->inc();
                break;
            case 'engine.step':
                $p = $event->data['pressure'] ?? null;
                if ($this->pressure !== null && (is_int($p) || is_float($p))) {
                    $this->pressure->labels($event->executionId)->set((float) $p);
                }
                $d = $event->data['delta'] ?? null;
                if ($this->stepDelta !== null && (is_int($d) || is_float($d))) {
                    $this->stepDelta->observe((float) $d);
                }
                break;
            default:
                // ignore
        }
    }
}
