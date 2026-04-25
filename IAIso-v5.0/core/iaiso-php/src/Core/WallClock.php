<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Real time, from {@link microtime(true)}. */
final class WallClock implements Clock
{
    private static ?WallClock $instance = null;

    public static function instance(): self
    {
        return self::$instance ??= new self();
    }

    public function now(): float
    {
        return microtime(true);
    }
}
