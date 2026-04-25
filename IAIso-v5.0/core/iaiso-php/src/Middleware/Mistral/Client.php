<?php

declare(strict_types=1);

namespace IAIso\Middleware\Mistral;

interface Client
{
    /** @param array<string,mixed> $params */
    public function chatComplete(array $params): Response;
}
