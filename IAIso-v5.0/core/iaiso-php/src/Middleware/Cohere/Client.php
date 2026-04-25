<?php

declare(strict_types=1);

namespace IAIso\Middleware\Cohere;

interface Client
{
    /** @param array<string,mixed> $params */
    public function chat(array $params): Response;
}
