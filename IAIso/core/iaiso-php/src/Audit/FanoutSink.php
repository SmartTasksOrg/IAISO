<?php

declare(strict_types=1);

namespace IAIso\Audit;

/** Forwards events to multiple sinks. */
final class FanoutSink implements Sink
{
    /** @var Sink[] */
    private array $sinks;

    public function __construct(Sink ...$sinks)
    {
        $this->sinks = $sinks;
    }

    public function emit(Event $event): void
    {
        foreach ($this->sinks as $sink) {
            try {
                $sink->emit($event);
            } catch (\Throwable) {
                // Sinks must not poison each other — swallow
            }
        }
    }
}
