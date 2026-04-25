<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Token's {@code jti} is on a revocation list. */
final class RevokedTokenException extends ConsentException
{
    public function __construct(public readonly string $jti)
    {
        parent::__construct("token revoked: $jti");
    }
}
