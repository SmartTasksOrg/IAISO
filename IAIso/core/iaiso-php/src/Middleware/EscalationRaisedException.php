<?php

declare(strict_types=1);

namespace IAIso\Middleware;

/** Raised when {@code raiseOnEscalation} is true and the engine has escalated. */
final class EscalationRaisedException extends MiddlewareException
{
    public function __construct()
    {
        parent::__construct('execution escalated; raise-on-escalation enabled');
    }
}
