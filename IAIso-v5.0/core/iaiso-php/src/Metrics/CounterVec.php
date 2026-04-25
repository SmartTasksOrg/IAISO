<?php

declare(strict_types=1);

namespace IAIso\Metrics;

interface CounterVec
{
    public function labels(string ...$values): Counter;
}
