<?php

declare(strict_types=1);

namespace IAIso\Middleware;

/** Raised when the execution is locked. */
final class LockedException extends MiddlewareException
{
    public function __construct()
    {
        parent::__construct('execution locked');
    }
}
