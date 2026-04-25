<?php

declare(strict_types=1);

namespace IAIso\Policy;

/** Arithmetic mean of per-execution pressures. */
final class MeanAggregator implements Aggregator
{
    public function name(): string { return 'mean'; }

    public function aggregate(array $pressures): float
    {
        if (count($pressures) === 0) return 0.0;
        return array_sum($pressures) / count($pressures);
    }
}
