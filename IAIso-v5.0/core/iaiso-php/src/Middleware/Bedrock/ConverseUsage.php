<?php

declare(strict_types=1);

namespace IAIso\Middleware\Bedrock;

final class ConverseUsage
{
    public function __construct(
        public readonly int $inputTokens = 0,
        public readonly int $outputTokens = 0,
        public readonly int $totalTokens = 0,
    ) {}
}
