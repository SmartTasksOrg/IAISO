<?php

declare(strict_types=1);

namespace IAIso\Middleware\OpenAi;

interface Client
{
    /** @param array<string,mixed> $params */
    public function chatCompletionsCreate(array $params): Response;
}
