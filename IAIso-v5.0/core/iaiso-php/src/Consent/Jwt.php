<?php

declare(strict_types=1);

namespace IAIso\Consent;

/**
 * Internal JWT codec. Hand-rolled HS256/RS256 using PHP's built-in
 * crypto extensions (`hash_hmac`, `openssl_sign`, `openssl_verify`).
 * No third-party JWT library required.
 */
final class Jwt
{
    private function __construct() {}

    /**
     * Encode bytes as base64url, no padding.
     */
    public static function b64UrlEncode(string $bytes): string
    {
        return rtrim(strtr(base64_encode($bytes), '+/', '-_'), '=');
    }

    /**
     * Decode a base64url-encoded string. Accepts with or without padding.
     */
    public static function b64UrlDecode(string $s): string
    {
        $padded = strtr($s, '-_', '+/');
        // Base64 input length must be a multiple of 4
        $rem = strlen($padded) % 4;
        if ($rem > 0) {
            $padded .= str_repeat('=', 4 - $rem);
        }
        $out = base64_decode($padded, true);
        if ($out === false) {
            throw new InvalidTokenException('malformed base64url segment');
        }
        return $out;
    }

    /**
     * Sign the given claims into a compact JWT.
     *
     * @param array<string,mixed> $claims
     * @param string|null $hsKey raw HMAC bytes (HS256)
     * @param resource|\OpenSSLAsymmetricKey|string|null $rsKey OpenSSL key (RS256)
     */
    public static function sign(Algorithm $alg, array $claims, ?string $hsKey, mixed $rsKey): string
    {
        $header = ['alg' => $alg->value, 'typ' => 'JWT'];
        $headerJson = self::canonicalEncode($header);
        $claimsJson = self::canonicalEncode($claims);
        $headerB64 = self::b64UrlEncode($headerJson);
        $claimsB64 = self::b64UrlEncode($claimsJson);
        $signingInput = $headerB64 . '.' . $claimsB64;

        $signature = match ($alg) {
            Algorithm::HS256 => self::hmacSha256($signingInput, $hsKey),
            Algorithm::RS256 => self::rsaSign($signingInput, $rsKey),
        };
        return $signingInput . '.' . self::b64UrlEncode($signature);
    }

    /**
     * Parse a compact JWT into its three deserialized parts. Does NOT
     * verify the signature — call {@see verifySignature()} for that.
     */
    public static function parse(string $token): ParsedJwt
    {
        $parts = explode('.', $token);
        if (count($parts) !== 3) {
            throw new InvalidTokenException('malformed JWT: expected 3 segments');
        }
        [$headerB64, $claimsB64, $sigB64] = $parts;
        try {
            $header = json_decode(self::b64UrlDecode($headerB64), true, 512, JSON_THROW_ON_ERROR);
            $claims = json_decode(self::b64UrlDecode($claimsB64), true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            throw new InvalidTokenException('malformed JWT JSON: ' . $e->getMessage());
        }
        if (!is_array($header) || !is_array($claims)) {
            throw new InvalidTokenException('JWT header/claims must be objects');
        }
        $signature = self::b64UrlDecode($sigB64);
        return new ParsedJwt($headerB64, $claimsB64, $sigB64, $header, $claims, $signature);
    }

    /**
     * Verify the signature on a parsed JWT.
     *
     * @param string|null $hsKey raw HMAC bytes (HS256)
     * @param resource|\OpenSSLAsymmetricKey|string|null $rsKey OpenSSL key or PEM (RS256)
     */
    public static function verifySignature(ParsedJwt $parsed, Algorithm $alg, ?string $hsKey, mixed $rsKey): bool
    {
        $signingInput = $parsed->headerB64 . '.' . $parsed->claimsB64;
        return match ($alg) {
            Algorithm::HS256 => hash_equals(
                self::hmacSha256($signingInput, $hsKey),
                $parsed->signature,
            ),
            Algorithm::RS256 => self::rsaVerify($signingInput, $parsed->signature, $rsKey),
        };
    }

    /**
     * Encode a value as JSON with a stable key order. PHP's
     * {@link json_encode} preserves insertion order, which is what we
     * want here — callers build claims in the order required.
     */
    public static function canonicalEncode(array $value): string
    {
        $out = json_encode($value,
            JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE | JSON_THROW_ON_ERROR);
        if ($out === false) {
            throw new InvalidTokenException('JSON encode failed');
        }
        return $out;
    }

    private static function hmacSha256(string $data, ?string $key): string
    {
        if ($key === null || $key === '') {
            throw new \InvalidArgumentException('HS256 requires a key');
        }
        return hash_hmac('sha256', $data, $key, true);
    }

    private static function rsaSign(string $data, mixed $key): string
    {
        if ($key === null) {
            throw new \InvalidArgumentException('RS256 requires a private key');
        }
        if (!openssl_sign($data, $sig, $key, OPENSSL_ALGO_SHA256)) {
            throw new \RuntimeException('RSA sign failed: ' . openssl_error_string());
        }
        return $sig;
    }

    private static function rsaVerify(string $data, string $signature, mixed $key): bool
    {
        if ($key === null) {
            return false;
        }
        $result = openssl_verify($data, $signature, $key, OPENSSL_ALGO_SHA256);
        return $result === 1;
    }
}
