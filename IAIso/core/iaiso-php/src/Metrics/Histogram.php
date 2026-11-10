<?php

declare(strict_types=1);

namespace IAIso\Metrics;

interface Histogram
{
    public function observe(float $v): void;
}
