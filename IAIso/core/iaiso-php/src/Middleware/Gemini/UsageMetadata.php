<?php

declare(strict_types=1);

namespace IAIso\Middleware\Gemini;

final class UsageMetadata
{
    public function __construct(
        public readonly int $promptTokenCount = 0,
        public readonly int $candidatesTokenCount = 0,
        public readonly int $totalTokenCount = 0,
    ) {
    }
}
