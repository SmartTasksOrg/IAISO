<?php

declare(strict_types=1);

namespace IAIso\Middleware\OpenAi;

final class Choice
{
    /** @param ToolCall[] $toolCalls */
    public function __construct(
        public readonly array $toolCalls = [],
        public readonly bool $hasFunctionCall = false,
    ) {
    }
}
