<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Identity;

use IAIso\Identity\IdentityException;
use IAIso\Identity\OidcVerifier;
use IAIso\Identity\ProviderConfig;
use IAIso\Identity\ScopeMapping;
use PHPUnit\Framework\TestCase;

final class IdentityTest extends TestCase
{
    public function testDeriveDirectClaimString(): void
    {
        $out = OidcVerifier::deriveScopes(
            ['scope' => 'tools.search tools.fetch'],
            ScopeMapping::defaults(),
        );
        self::assertContains('tools.search', $out);
        self::assertContains('tools.fetch', $out);
    }

    public function testDeriveDirectClaimArray(): void
    {
        $out = OidcVerifier::deriveScopes(
            ['scp' => ['a.b', 'c']],
            ScopeMapping::defaults(),
        );
        self::assertSame(['a.b', 'c'], $out);
    }

    public function testDeriveGroupToScopes(): void
    {
        $out = OidcVerifier::deriveScopes(
            ['groups' => ['engineers']],
            new ScopeMapping([], ['engineers' => ['tools.search', 'tools.fetch']]),
        );
        self::assertContains('tools.search', $out);
        self::assertContains('tools.fetch', $out);
    }

    public function testAlwaysGrantAdded(): void
    {
        $out = OidcVerifier::deriveScopes([], new ScopeMapping([], [], ['base']));
        self::assertSame(['base'], $out);
    }

    public function testPresetsHaveExpectedEndpoints(): void
    {
        $okta = ProviderConfig::okta('acme.okta.com', 'api');
        self::assertStringContainsString('acme.okta.com', $okta->discoveryUrl);

        $auth0 = ProviderConfig::auth0('acme.auth0.com', 'api');
        self::assertStringEndsWith('/', $auth0->issuer);

        $azure = ProviderConfig::azureAd('tenant-id', 'api', true);
        self::assertStringContainsString('v2.0', $azure->discoveryUrl);
    }

    public function testVerifyFailsWhenJwksNotLoaded(): void
    {
        $v = new OidcVerifier(ProviderConfig::defaults());
        $this->expectException(IdentityException::class);
        $v->verify('a.b.c');
    }

    public function testRsaVerifyRoundtrip(): void
    {
        $privKey = openssl_pkey_new([
            'private_key_bits' => 2048,
            'private_key_type' => OPENSSL_KEYTYPE_RSA,
        ]);
        self::assertNotFalse($privKey);
        $details = openssl_pkey_get_details($privKey);
        self::assertIsArray($details);

        $kid = 'test-key';
        $headerJson = json_encode(['alg' => 'RS256', 'typ' => 'JWT', 'kid' => $kid]);
        $claims = [
            'iss' => 'https://test',
            'sub' => 'user-1',
            'aud' => 'myapi',
            'exp' => time() + 3600,
            'iat' => time(),
        ];
        $claimsJson = json_encode($claims);
        $h = \IAIso\Consent\Jwt::b64UrlEncode($headerJson);
        $c = \IAIso\Consent\Jwt::b64UrlEncode($claimsJson);
        openssl_sign("$h.$c", $sig, $privKey, OPENSSL_ALGO_SHA256);
        $token = "$h.$c." . \IAIso\Consent\Jwt::b64UrlEncode($sig);

        $jwks = json_encode([
            'keys' => [[
                'kty' => 'RSA',
                'kid' => $kid,
                'alg' => 'RS256',
                'use' => 'sig',
                'n' => \IAIso\Consent\Jwt::b64UrlEncode($details['rsa']['n']),
                'e' => \IAIso\Consent\Jwt::b64UrlEncode($details['rsa']['e']),
            ]],
        ]);

        $cfg = new ProviderConfig(null, null, 'https://test', 'myapi', ['RS256'], 5);
        $v = new OidcVerifier($cfg);
        $v->setJwksFromBytes($jwks);
        $verified = $v->verify($token);
        self::assertSame('user-1', $verified['sub']);
    }
}
