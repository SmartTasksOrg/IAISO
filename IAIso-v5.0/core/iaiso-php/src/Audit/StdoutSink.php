<?php

declare(strict_types=1);

namespace IAIso\Audit;

/** Writes one JSON object per event to STDOUT. */
final class StdoutSink implements Sink
{
    private static ?StdoutSink $instance = null;

    public static function instance(): self
    {
        return self::$instance ??= new self();
    }

    public function emit(Event $event): void
    {
        echo $event->toJson() . PHP_EOL;
    }
}
