<?php

declare(strict_types=1);

namespace IAIso\Audit;

/** Discards events. */
final class NullSink implements Sink
{
    private static ?NullSink $instance = null;

    public static function instance(): self
    {
        return self::$instance ??= new self();
    }

    public function emit(Event $event): void
    {
        // intentionally empty
    }
}
