<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Token's {@code exp} claim has passed. */
final class ExpiredTokenException extends ConsentException
{
    public function __construct()
    {
        parent::__construct('token expired');
    }
}
