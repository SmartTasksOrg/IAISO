<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Closure-based clock. */
final class CallbackClock implements Clock
{
    /** @param callable():float $fn */
    public function __construct(private $fn)
    {
    }

    public function now(): float
    {
        return ($this->fn)();
    }
}
