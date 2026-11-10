<?php

declare(strict_types=1);

namespace IAIso\Identity;

final class Jwks
{
    /** @param Jwk[] $keys */
    public function __construct(public readonly array $keys) {}
}
