<?php

declare(strict_types=1);

namespace IAIso\Identity;

/** A single key from a JWKS document. */
final class Jwk
{
    public function __construct(
        public readonly string $kty,
        public readonly ?string $kid = null,
        public readonly ?string $alg = null,
        public readonly ?string $use = null,
        public readonly ?string $n = null,
        public readonly ?string $e = null,
    ) {}
}
