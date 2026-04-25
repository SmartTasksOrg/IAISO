<?php

declare(strict_types=1);

namespace IAIso\Metrics;

interface GaugeVec
{
    public function labels(string ...$values): Gauge;
}
