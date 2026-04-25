<?php

declare(strict_types=1);

namespace IAIso\Metrics;

interface Counter
{
    public function inc(): void;
}
