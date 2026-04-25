<?php

declare(strict_types=1);

namespace IAIso\Metrics;

interface Gauge
{
    public function set(float $v): void;
}
