<?php

declare(strict_types=1);

namespace IAIso\Middleware\Cohere;

final class BilledUnits
{
    public function __construct(
        public readonly int $inputTokens = 0,
        public readonly int $outputTokens = 0,
    ) {}
}
