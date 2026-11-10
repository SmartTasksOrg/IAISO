<?php

declare(strict_types=1);

namespace IAIso\Middleware\Bedrock;

final class InvokeResponse
{
    public function __construct(
        public readonly string $modelId = '',
        public readonly string $body = '',
    ) {}
}
