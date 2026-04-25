<?php

declare(strict_types=1);

namespace IAIso\Identity;

/** Configuration for an {@see OidcVerifier}. */
final class ProviderConfig
{
    /** @param string[] $allowedAlgorithms */
    public function __construct(
        public readonly ?string $discoveryUrl = null,
        public readonly ?string $jwksUrl = null,
        public readonly ?string $issuer = null,
        public readonly ?string $audience = null,
        public readonly array $allowedAlgorithms = ['RS256'],
        public readonly int $leewaySeconds = 5,
    ) {}

    public static function defaults(): self
    {
        return new self();
    }

    /** Build a {@see ProviderConfig} for Okta. */
    public static function okta(string $domain, string $audience): self
    {
        return new self(
            discoveryUrl: "https://$domain/.well-known/openid-configuration",
            issuer: "https://$domain",
            audience: $audience,
        );
    }

    /** Build a {@see ProviderConfig} for Auth0. */
    public static function auth0(string $domain, string $audience): self
    {
        return new self(
            discoveryUrl: "https://$domain/.well-known/openid-configuration",
            issuer: "https://$domain/",
            audience: $audience,
        );
    }

    /** Build a {@see ProviderConfig} for Azure AD / Entra. */
    public static function azureAd(string $tenant, string $audience, bool $v2 = true): self
    {
        $base = $v2
            ? "https://login.microsoftonline.com/$tenant/v2.0"
            : "https://login.microsoftonline.com/$tenant";
        return new self(
            discoveryUrl: "$base/.well-known/openid-configuration",
            issuer: $base,
            audience: $audience,
        );
    }
}
