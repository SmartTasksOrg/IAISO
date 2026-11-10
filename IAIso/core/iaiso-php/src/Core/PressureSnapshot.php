<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Read-only snapshot of engine state. */
final class PressureSnapshot
{
    public function __construct(
        public readonly float $pressure,
        public readonly int $step,
        public readonly Lifecycle $lifecycle,
        public readonly float $lastStepAt,
    ) {
    }
}
