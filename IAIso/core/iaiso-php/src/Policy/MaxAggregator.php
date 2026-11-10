<?php

declare(strict_types=1);

namespace IAIso\Policy;

/** Maximum of per-execution pressures. */
final class MaxAggregator implements Aggregator
{
    public function name(): string { return 'max'; }

    public function aggregate(array $pressures): float
    {
        if (count($pressures) === 0) return 0.0;
        return (float) max($pressures);
    }
}
