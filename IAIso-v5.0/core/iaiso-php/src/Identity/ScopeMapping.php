<?php

declare(strict_types=1);

namespace IAIso\Identity;

/** Configures how OIDC claims become IAIso scopes. */
final class ScopeMapping
{
    /**
     * @param string[] $directClaims
     * @param array<string,string[]> $groupToScopes
     * @param string[] $alwaysGrant
     */
    public function __construct(
        public readonly array $directClaims = [],
        public readonly array $groupToScopes = [],
        public readonly array $alwaysGrant = [],
    ) {}

    public static function defaults(): self
    {
        return new self();
    }
}
