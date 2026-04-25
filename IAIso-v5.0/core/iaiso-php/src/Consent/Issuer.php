<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Issues consent tokens. */
final class Issuer
{
    /**
     * @param string|null $hsKey raw HMAC bytes (HS256)
     * @param resource|\OpenSSLAsymmetricKey|string|null $rsKey OpenSSL private key (RS256)
     * @param callable():int $clock seconds-since-epoch clock
     */
    public function __construct(
        private readonly ?string $hsKey,
        private readonly mixed $rsKey,
        private readonly Algorithm $algorithm,
        private readonly string $issuer,
        private readonly int $defaultTtlSeconds,
        private $clock,
    ) {
        if (!is_callable($this->clock)) {
            throw new \InvalidArgumentException('clock must be callable returning int seconds');
        }
    }

    public static function builder(): IssuerBuilder
    {
        return new IssuerBuilder();
    }

    /**
     * Issue a fresh token.
     *
     * @param string[] $scopes
     * @param array<string,mixed>|null $metadata
     */
    public function issue(
        string $subject,
        array $scopes,
        ?string $executionId = null,
        ?int $ttlSeconds = null,
        ?array $metadata = null,
    ): Scope {
        $now = ($this->clock)();
        $ttl = $ttlSeconds ?? $this->defaultTtlSeconds;
        $exp = $now + $ttl;
        $jti = bin2hex(random_bytes(16));
        // Spec field order: iss, sub, iat, exp, jti, scopes, [execution_id], [metadata]
        $claims = [
            'iss' => $this->issuer,
            'sub' => $subject,
            'iat' => $now,
            'exp' => $exp,
            'jti' => $jti,
            'scopes' => $scopes,
        ];
        if ($executionId !== null) {
            $claims['execution_id'] = $executionId;
        }
        if ($metadata !== null && count($metadata) > 0) {
            $claims['metadata'] = $metadata;
        }
        $token = Jwt::sign($this->algorithm, $claims, $this->hsKey, $this->rsKey);
        return new Scope(
            token: $token,
            subject: $subject,
            scopes: $scopes,
            executionId: $executionId,
            jti: $jti,
            issuedAt: $now,
            expiresAt: $exp,
            metadata: $metadata ?? [],
        );
    }

    /** Generate a 64-byte base64url-no-pad HS256 secret. */
    public static function generateHs256Secret(): string
    {
        return Jwt::b64UrlEncode(random_bytes(64));
    }
}
