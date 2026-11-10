<?php

declare(strict_types=1);

namespace IAIso\Observability;

use IAIso\Audit\Event;
use IAIso\Audit\Sink;

/**
 * IAIso OpenTelemetry tracing sink.
 *
 * <p>Structurally typed against the OTel trace API. The official
 * {@code open-telemetry/opentelemetry} packages' Tracer and Span
 * interfaces satisfy these structural contracts with thin adapters.
 */
final class OtelSpanSink implements Sink
{
    /** @var array<string,Span> */
    private array $spans = [];

    public function __construct(
        private readonly Tracer $tracer,
        private readonly string $spanName = 'iaiso.execution',
    ) {
    }

    /** End any open spans. Useful at shutdown. */
    public function closeAll(): void
    {
        foreach ($this->spans as $s) {
            try { $s->end(); } catch (\Throwable) {}
        }
        $this->spans = [];
    }

    public function emit(Event $event): void
    {
        if ($event->kind === 'engine.init') {
            $span = $this->tracer->startSpan(
                $this->spanName . ':' . $event->executionId,
                ['iaiso.execution_id' => $event->executionId],
            );
            $this->spans[$event->executionId] = $span;
        } else {
            $span = $this->spans[$event->executionId] ?? null;
        }
        if ($span === null) return;

        $attrs = $event->data;
        $attrs['iaiso.schema_version'] = $event->schemaVersion;
        $span->addEvent($event->kind, $attrs);

        switch ($event->kind) {
            case 'engine.step':
                if (isset($event->data['pressure'])) {
                    $span->setAttribute('iaiso.pressure', $event->data['pressure']);
                }
                break;
            case 'engine.escalation':
                $span->setAttribute('iaiso.escalated', true);
                break;
            case 'engine.release':
                $span->setAttribute('iaiso.released', true);
                break;
            case 'execution.closed':
                $span->end();
                unset($this->spans[$event->executionId]);
                break;
        }
    }
}
