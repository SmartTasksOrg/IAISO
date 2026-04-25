<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Parsed JWT (signature not yet verified). */
final class ParsedJwt
{
    public function __construct(
        public readonly string $headerB64,
        public readonly string $claimsB64,
        public readonly string $signatureB64,
        /** @var array<string,mixed> */
        public readonly array $header,
        /** @var array<string,mixed> */
        public readonly array $claims,
        public readonly string $signature,
    ) {
    }
}
