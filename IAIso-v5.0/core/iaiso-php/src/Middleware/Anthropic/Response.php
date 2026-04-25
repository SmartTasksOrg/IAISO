<?php

declare(strict_types=1);

namespace IAIso\Middleware\Anthropic;

/** Anthropic response — minimal subset of fields we account against. */
final class Response
{
    /** @param ContentBlock[] $content */
    public function __construct(
        public readonly string $model,
        public readonly int $inputTokens,
        public readonly int $outputTokens,
        public readonly array $content,
    ) {
    }
}
