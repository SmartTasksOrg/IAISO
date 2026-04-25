<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Thread-safe-ish set of revoked JTIs. */
final class RevocationList
{
    /** @var array<string,bool> */
    private array $set = [];

    public function revoke(string $jti): void
    {
        $this->set[$jti] = true;
    }

    public function isRevoked(string $jti): bool
    {
        return isset($this->set[$jti]);
    }

    public function clear(): void
    {
        $this->set = [];
    }
}
