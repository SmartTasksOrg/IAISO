<?php

declare(strict_types=1);

namespace IAIso\Middleware\Cohere;

final class Response
{
    /** @param ToolCall[] $toolCalls */
    public function __construct(
        public readonly string $model,
        public readonly Meta $meta,
        public readonly array $toolCalls = [],
    ) {}
}
