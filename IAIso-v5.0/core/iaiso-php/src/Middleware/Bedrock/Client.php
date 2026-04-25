<?php

declare(strict_types=1);

namespace IAIso\Middleware\Bedrock;

interface Client
{
    /** @param array<string,mixed> $params */
    public function converse(array $params): ConverseResponse;
    /** @param array<string,mixed> $params */
    public function invokeModel(array $params): InvokeResponse;
}
