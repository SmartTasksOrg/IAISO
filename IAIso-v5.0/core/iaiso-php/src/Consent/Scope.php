<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** A verified consent scope. */
final class Scope
{
    public function __construct(
        public readonly string $token,
        public readonly string $subject,
        /** @var string[] */
        public readonly array $scopes,
        public readonly ?string $executionId,
        public readonly string $jti,
        public readonly int $issuedAt,
        public readonly int $expiresAt,
        /** @var array<string,mixed> */
        public readonly array $metadata = [],
    ) {
    }

    /** True iff the verified scope set grants {@code $requested}. */
    public function grants(string $requested): bool
    {
        return Scopes::granted($this->scopes, $requested);
    }

    /** Throws {@see InsufficientScopeException} if any of {@code $required} is not granted. */
    public function requireScopes(array $required): void
    {
        foreach ($required as $r) {
            if (!$this->grants($r)) {
                throw new InsufficientScopeException(
                    "scope '$r' not granted; have [" . implode(', ', $this->scopes) . ']');
            }
        }
    }
}
