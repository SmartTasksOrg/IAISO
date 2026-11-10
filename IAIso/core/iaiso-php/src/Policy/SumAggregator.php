<?php

declare(strict_types=1);

namespace IAIso\Policy;

/** Sum of per-execution pressures. */
final class SumAggregator implements Aggregator
{
    public function name(): string { return 'sum'; }

    public function aggregate(array $pressures): float
    {
        return array_sum($pressures);
    }
}
