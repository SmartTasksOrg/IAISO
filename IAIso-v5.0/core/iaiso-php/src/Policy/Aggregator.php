<?php

declare(strict_types=1);

namespace IAIso\Policy;

/** A coordinator aggregation strategy. */
interface Aggregator
{
    /** Wire-format aggregator name. */
    public function name(): string;

    /**
     * Compute the aggregate from per-execution pressures.
     *
     * @param array<string,float> $pressures
     */
    public function aggregate(array $pressures): float;
}
