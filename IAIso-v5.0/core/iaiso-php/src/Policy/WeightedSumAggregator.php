<?php

declare(strict_types=1);

namespace IAIso\Policy;

/** Weighted sum of per-execution pressures. */
final class WeightedSumAggregator implements Aggregator
{
    /**
     * @param array<string,float> $weights
     */
    public function __construct(
        public readonly array $weights,
        public readonly float $defaultWeight,
    ) {
    }

    public function name(): string { return 'weighted_sum'; }

    public function aggregate(array $pressures): float
    {
        $total = 0.0;
        foreach ($pressures as $k => $v) {
            $w = $this->weights[$k] ?? $this->defaultWeight;
            $total += $w * $v;
        }
        return $total;
    }
}
