<?php

declare(strict_types=1);

namespace IAIso\Middleware\Mistral;

final class Response
{
    /** @param Choice[] $choices */
    public function __construct(
        public readonly string $model,
        public readonly Usage $usage,
        public readonly array $choices,
    ) {}
}
