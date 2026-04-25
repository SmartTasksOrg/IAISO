<?php

declare(strict_types=1);

namespace IAIso\Middleware\Anthropic;

/** Structural client interface — one method per Anthropic operation. */
interface Client
{
    /** @param array<string,mixed> $params */
    public function messagesCreate(array $params): Response;
}
