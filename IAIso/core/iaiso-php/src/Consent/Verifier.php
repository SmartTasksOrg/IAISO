<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Verifies signed consent tokens. */
final class Verifier
{
    /**
     * @param string|null $hsKey raw HMAC bytes (HS256)
     * @param resource|\OpenSSLAsymmetricKey|string|null $rsKey OpenSSL public key (RS256)
     * @param callable():int $clock seconds-since-epoch clock
     */
    public function __construct(
        private readonly ?string $hsKey,
        private readonly mixed $rsKey,
        private readonly Algorithm $algorithm,
        private readonly string $issuer,
        private readonly ?RevocationList $revocationList,
        private readonly int $leewaySeconds,
        private $clock,
    ) {
    }

    public static function builder(): VerifierBuilder
    {
        return new VerifierBuilder();
    }

    /**
     * Verify {@code $token}. If {@code $requestedExecutionId} is non-null
     * and the token is bound to a different execution, throws
     * {@see InvalidTokenException}.
     */
    public function verify(string $token, ?string $requestedExecutionId = null): Scope
    {
        $parsed = Jwt::parse($token);

        // Algorithm check from header
        $alg = $parsed->header['alg'] ?? null;
        if ($alg !== $this->algorithm->value) {
            throw new InvalidTokenException(
                'unexpected algorithm: ' . ($alg ?? 'missing'));
        }

        if (!Jwt::verifySignature($parsed, $this->algorithm, $this->hsKey, $this->rsKey)) {
            throw new InvalidTokenException('signature verification failed');
        }

        $claims = $parsed->claims;
        foreach (['exp', 'iat', 'iss', 'sub', 'jti'] as $req) {
            if (!array_key_exists($req, $claims)) {
                throw new InvalidTokenException("missing required claim: $req");
            }
        }

        if ($claims['iss'] !== $this->issuer) {
            throw new InvalidTokenException(
                "iss mismatch: got {$claims['iss']}, want {$this->issuer}");
        }

        $now = ($this->clock)();
        $exp = (int) $claims['exp'];
        if ($exp + $this->leewaySeconds < $now) {
            throw new ExpiredTokenException();
        }

        $jti = (string) $claims['jti'];
        if ($this->revocationList !== null && $this->revocationList->isRevoked($jti)) {
            throw new RevokedTokenException($jti);
        }

        $tokenExec = $claims['execution_id'] ?? null;
        if ($requestedExecutionId !== null && $tokenExec !== null
                && $tokenExec !== $requestedExecutionId) {
            throw new InvalidTokenException(
                "token bound to $tokenExec, requested $requestedExecutionId");
        }

        $scopes = $claims['scopes'] ?? [];
        if (!is_array($scopes)) {
            throw new InvalidTokenException('scopes claim must be an array');
        }
        $metadata = $claims['metadata'] ?? [];
        if (!is_array($metadata)) {
            $metadata = [];
        }

        return new Scope(
            token: $token,
            subject: (string) $claims['sub'],
            scopes: array_values(array_map('strval', $scopes)),
            executionId: $tokenExec !== null ? (string) $tokenExec : null,
            jti: $jti,
            issuedAt: (int) $claims['iat'],
            expiresAt: $exp,
            metadata: $metadata,
        );
    }
}
