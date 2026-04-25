<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Pre-recorded clock values; deterministic for tests. */
final class ScriptedClock implements Clock
{
    private int $idx = 0;

    /** @param float[] $sequence */
    public function __construct(private array $sequence)
    {
    }

    public function now(): float
    {
        if (count($this->sequence) === 0) return 0.0;
        $i = $this->idx++;
        return $this->sequence[$i] ?? $this->sequence[count($this->sequence) - 1];
    }

    public function reset(): void
    {
        $this->idx = 0;
    }
}
