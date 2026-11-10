<?php

declare(strict_types=1);

namespace IAIso\Middleware\Bedrock;

final class ConverseResponse
{
    /** @param ConverseContentBlock[] $content */
    public function __construct(
        public readonly ConverseUsage $usage,
        public readonly array $content,
    ) {
    }
}
