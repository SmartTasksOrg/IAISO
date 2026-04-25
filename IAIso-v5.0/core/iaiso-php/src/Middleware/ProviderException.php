<?php

declare(strict_types=1);

namespace IAIso\Middleware;

/** Raised when the upstream provider call failed. */
final class ProviderException extends MiddlewareException
{
    public function __construct(string $message, ?\Throwable $previous = null)
    {
        parent::__construct("provider error: $message", 0, $previous);
    }
}
