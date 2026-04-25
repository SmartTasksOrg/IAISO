<?php

declare(strict_types=1);

namespace IAIso\Policy;

/** Consent-section configuration from a parsed policy. */
final class ConsentPolicy
{
    /**
     * @param string[] $requiredScopes
     * @param string[] $allowedAlgorithms
     */
    public function __construct(
        public readonly ?string $issuer = null,
        public readonly float $defaultTtlSeconds = 3600.0,
        public readonly array $requiredScopes = [],
        public readonly array $allowedAlgorithms = ['HS256', 'RS256'],
    ) {
    }

    public static function defaults(): self
    {
        return new self();
    }
}
