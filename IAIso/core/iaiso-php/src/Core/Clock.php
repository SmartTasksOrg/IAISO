<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Source of monotonic-ish double-precision seconds since the epoch. */
interface Clock
{
    public function now(): float;
}
