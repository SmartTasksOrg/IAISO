<?php

declare(strict_types=1);

namespace IAIso\Identity;

use IAIso\Consent\Issuer;
use IAIso\Consent\Jwt;
use IAIso\Consent\Scope;

/**
 * IAIso OIDC identity verifier.
 *
 * <p>This class is HTTP-free. Caller fetches JWKS bytes (using
 * {@link curl_exec()}, Guzzle, Symfony HttpClient, or any HTTP
 * library) and passes them to {@see setJwksFromBytes()}. This keeps
 * the SDK dependency-light and lets users use whichever HTTP client
 * they prefer.
 */
final class OidcVerifier
{
    private ?Jwks $jwks = null;

    public function __construct(private readonly ProviderConfig $cfg)
    {
    }

    /** Inject pre-fetched JWKS bytes into the verifier's cache. */
    public function setJwksFromBytes(string $body): void
    {
        try {
            $root = json_decode($body, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            throw new IdentityException('JWKS parse failed: ' . $e->getMessage(), 0, $e);
        }
        if (!is_array($root) || !isset($root['keys']) || !is_array($root['keys'])) {
            throw new IdentityException('JWKS missing keys array');
        }
        $keys = [];
        foreach ($root['keys'] as $k) {
            if (!is_array($k)) continue;
            $keys[] = new Jwk(
                kty: (string) ($k['kty'] ?? ''),
                kid: isset($k['kid']) ? (string) $k['kid'] : null,
                alg: isset($k['alg']) ? (string) $k['alg'] : null,
                use: isset($k['use']) ? (string) $k['use'] : null,
                n:   isset($k['n']) ? (string) $k['n'] : null,
                e:   isset($k['e']) ? (string) $k['e'] : null,
            );
        }
        $this->jwks = new Jwks($keys);
    }

    /**
     * Verify a token against the cached JWKS.
     *
     * @return array<string,mixed> the verified claims
     */
    public function verify(string $token): array
    {
        if ($this->jwks === null) {
            throw new IdentityException('oidc: JWKS not loaded; call setJwksFromBytes() first');
        }
        $parts = explode('.', $token);
        if (count($parts) !== 3) {
            throw new IdentityException('oidc: malformed JWT');
        }
        try {
            $header = json_decode(Jwt::b64UrlDecode($parts[0]), true, 512, JSON_THROW_ON_ERROR);
            $claims = json_decode(Jwt::b64UrlDecode($parts[1]), true, 512, JSON_THROW_ON_ERROR);
            $signature = Jwt::b64UrlDecode($parts[2]);
        } catch (\JsonException $e) {
            throw new IdentityException('oidc: malformed JWT JSON', 0, $e);
        }
        if (!is_array($header) || !is_array($claims)) {
            throw new IdentityException('oidc: malformed JWT');
        }

        $alg = $header['alg'] ?? '';
        if (!in_array($alg, $this->cfg->allowedAlgorithms, true)) {
            throw new IdentityException("oidc: algorithm not allowed: $alg");
        }
        $kid = $header['kid'] ?? '';

        // Find matching key
        $match = null;
        foreach ($this->jwks->keys as $k) {
            if ($k->kid !== null && $k->kid === $kid) {
                $match = $k;
                break;
            }
        }
        if ($match === null && count($this->jwks->keys) === 1 && $kid === '') {
            $match = $this->jwks->keys[0];
        }
        if ($match === null) {
            throw new IdentityException("oidc: kid $kid not found in JWKS");
        }
        if ($match->kty !== 'RSA') {
            throw new IdentityException("oidc: unsupported key type: $match->kty");
        }

        // Build PEM from modulus + exponent
        $pem = self::rsaPublicKeyPem($match->n ?? '', $match->e ?? '');
        $signingInput = $parts[0] . '.' . $parts[1];
        $result = openssl_verify($signingInput, $signature, $pem, OPENSSL_ALGO_SHA256);
        if ($result !== 1) {
            throw new IdentityException('oidc: signature verification failed');
        }

        // Issuer check
        if ($this->cfg->issuer !== null && $this->cfg->issuer !== '') {
            $iss = $claims['iss'] ?? '';
            if ($iss !== $this->cfg->issuer) {
                throw new IdentityException(
                    "oidc: iss mismatch: got $iss, want {$this->cfg->issuer}");
            }
        }

        // Expiry
        if (isset($claims['exp'])) {
            $exp = (int) $claims['exp'];
            $now = time();
            if ($exp + $this->cfg->leewaySeconds < $now) {
                throw new IdentityException('oidc: token expired');
            }
        }

        // Audience
        if ($this->cfg->audience !== null && $this->cfg->audience !== '') {
            if (!self::audienceMatches($claims['aud'] ?? null, $this->cfg->audience)) {
                throw new IdentityException(
                    "oidc: aud mismatch (expected {$this->cfg->audience})");
            }
        }
        return $claims;
    }

    /**
     * Convert verified claims into a deduplicated list of IAIso scopes.
     *
     * @param array<string,mixed> $claims
     * @return string[]
     */
    public static function deriveScopes(array $claims, ScopeMapping $mapping): array
    {
        $directClaims = count($mapping->directClaims) === 0
            ? ['scp', 'scope', 'permissions']
            : $mapping->directClaims;

        $seen = [];
        foreach ($directClaims as $c) {
            if (!isset($claims[$c])) continue;
            $val = $claims[$c];
            if (is_string($val)) {
                $tokens = preg_split('/[\s,]+/', $val);
                foreach ($tokens as $tok) {
                    if ($tok !== '') $seen[$tok] = true;
                }
            } elseif (is_array($val)) {
                foreach ($val as $i) {
                    if (is_string($i)) $seen[$i] = true;
                }
            }
        }
        $groups = [];
        foreach (['groups', 'roles'] as $c) {
            if (isset($claims[$c]) && is_array($claims[$c])) {
                foreach ($claims[$c] as $g) {
                    if (is_string($g)) $groups[] = $g;
                }
            }
        }
        foreach ($groups as $g) {
            if (isset($mapping->groupToScopes[$g])) {
                foreach ($mapping->groupToScopes[$g] as $s) {
                    $seen[$s] = true;
                }
            }
        }
        foreach ($mapping->alwaysGrant as $s) $seen[$s] = true;
        return array_keys($seen);
    }

    /**
     * Mint an IAIso consent scope from a verified OIDC identity.
     */
    public static function issueFromOidc(
        OidcVerifier $verifier,
        Issuer $issuer,
        string $token,
        ScopeMapping $mapping,
        int $ttlSeconds = 3600,
        ?string $executionId = null,
    ): Scope {
        $claims = $verifier->verify($token);
        $subject = (string) ($claims['sub'] ?? 'unknown');
        $scopes = self::deriveScopes($claims, $mapping);

        $metadata = [];
        foreach (['iss' => 'oidc_iss', 'jti' => 'oidc_jti', 'aud' => 'oidc_aud'] as $src => $dst) {
            if (isset($claims[$src])) $metadata[$dst] = $claims[$src];
        }
        return $issuer->issue($subject, $scopes, $executionId, $ttlSeconds,
            count($metadata) > 0 ? $metadata : null);
    }

    private static function audienceMatches(mixed $aud, string $want): bool
    {
        if ($aud === null) return false;
        if (is_string($aud)) return $aud === $want;
        if (is_array($aud)) {
            foreach ($aud as $a) {
                if (is_string($a) && $a === $want) return true;
            }
        }
        return false;
    }

    /**
     * Build an RSA public key PEM from base64url-encoded modulus and
     * exponent (per RFC 7517). Returns a PEM string usable with
     * {@link openssl_verify()}.
     */
    private static function rsaPublicKeyPem(string $nB64, string $eB64): string
    {
        $n = Jwt::b64UrlDecode($nB64);
        $e = Jwt::b64UrlDecode($eB64);

        $modulus = self::asn1Integer($n);
        $exponent = self::asn1Integer($e);
        $rsaSeq = self::asn1Sequence($modulus . $exponent);

        // SubjectPublicKeyInfo:
        //   SEQUENCE { algorithm SEQUENCE { OID rsaEncryption, NULL }, BIT STRING { rsaSeq } }
        $rsaOid = "\x06\x09\x2a\x86\x48\x86\xf7\x0d\x01\x01\x01"; // rsaEncryption
        $algId = self::asn1Sequence($rsaOid . "\x05\x00");        // NULL params
        $bitString = "\x00" . $rsaSeq;
        $spkBitString = self::asn1Tag(0x03, $bitString);          // BIT STRING
        $spki = self::asn1Sequence($algId . $spkBitString);

        return "-----BEGIN PUBLIC KEY-----\n"
            . chunk_split(base64_encode($spki), 64, "\n")
            . "-----END PUBLIC KEY-----\n";
    }

    /** ASN.1 INTEGER (big-endian, prepend 0x00 if high bit set). */
    private static function asn1Integer(string $bytes): string
    {
        if (strlen($bytes) > 0 && (ord($bytes[0]) & 0x80) !== 0) {
            $bytes = "\x00" . $bytes;
        }
        return self::asn1Tag(0x02, $bytes);
    }

    private static function asn1Sequence(string $contents): string
    {
        return self::asn1Tag(0x30, $contents);
    }

    private static function asn1Tag(int $tag, string $contents): string
    {
        $len = strlen($contents);
        if ($len < 0x80) {
            $lengthEnc = chr($len);
        } else {
            // Long-form length
            $lenBytes = '';
            $tmp = $len;
            while ($tmp > 0) {
                $lenBytes = chr($tmp & 0xff) . $lenBytes;
                $tmp >>= 8;
            }
            $lengthEnc = chr(0x80 | strlen($lenBytes)) . $lenBytes;
        }
        return chr($tag) . $lengthEnc . $contents;
    }
}
