<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Consent;

use IAIso\Consent\Algorithm;
use IAIso\Consent\ExpiredTokenException;
use IAIso\Consent\InvalidTokenException;
use IAIso\Consent\Issuer;
use IAIso\Consent\RevocationList;
use IAIso\Consent\RevokedTokenException;
use IAIso\Consent\Scopes;
use IAIso\Consent\Verifier;
use PHPUnit\Framework\TestCase;

final class ConsentTest extends TestCase
{
    private const SECRET = 'test_secret_long_enough_for_hs256_security_xx';

    public function testScopeExactMatch(): void
    {
        self::assertTrue(Scopes::granted(['tools.search'], 'tools.search'));
    }

    public function testScopePrefixAtBoundary(): void
    {
        self::assertTrue(Scopes::granted(['tools'], 'tools.search'));
    }

    public function testScopeSubstringNotBoundary(): void
    {
        self::assertFalse(Scopes::granted(['tools'], 'toolsbar'));
    }

    public function testScopeMoreSpecificDoesntSatisfyLessSpecific(): void
    {
        self::assertFalse(Scopes::granted(['tools.search.bulk'], 'tools.search'));
    }

    public function testEmptyRequestedThrows(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        Scopes::granted(['tools'], '');
    }

    public function testIssueVerifyRoundtrip(): void
    {
        $issuer = Issuer::builder()
            ->hsKey(self::SECRET)->algorithm(Algorithm::HS256)
            ->issuer('iaiso')->clock(fn() => 1_700_000_000)->build();
        $scope = $issuer->issue('user-1', ['tools.search', 'tools.fetch']);
        self::assertNotEmpty($scope->token);

        $verifier = Verifier::builder()
            ->hsKey(self::SECRET)->algorithm(Algorithm::HS256)
            ->issuer('iaiso')->clock(fn() => 1_700_000_001)->build();
        $verified = $verifier->verify($scope->token);
        self::assertSame('user-1', $verified->subject);
        self::assertTrue($verified->grants('tools.search'));
    }

    public function testVerifyRejectsExpired(): void
    {
        $issuer = Issuer::builder()->hsKey(self::SECRET)
            ->clock(fn() => 1_700_000_000)->build();
        $scope = $issuer->issue('u', ['tools'], null, 1);

        $verifier = Verifier::builder()->hsKey(self::SECRET)
            ->clock(fn() => 1_700_000_010)->build();
        $this->expectException(ExpiredTokenException::class);
        $verifier->verify($scope->token);
    }

    public function testVerifyHonorsRevocation(): void
    {
        $issuer = Issuer::builder()->hsKey(self::SECRET)
            ->clock(fn() => 1_700_000_000)->build();
        $scope = $issuer->issue('u', ['tools']);
        $rl = new RevocationList();
        $rl->revoke($scope->jti);

        $verifier = Verifier::builder()->hsKey(self::SECRET)
            ->revocationList($rl)->clock(fn() => 1_700_000_001)->build();
        $this->expectException(RevokedTokenException::class);
        $verifier->verify($scope->token);
    }

    public function testVerifyHonorsExecutionBinding(): void
    {
        $issuer = Issuer::builder()->hsKey(self::SECRET)
            ->clock(fn() => 1_700_000_000)->build();
        $scope = $issuer->issue('u', ['tools'], 'exec-abc');

        $verifier = Verifier::builder()->hsKey(self::SECRET)
            ->clock(fn() => 1_700_000_001)->build();
        $this->expectException(InvalidTokenException::class);
        $verifier->verify($scope->token, 'exec-xyz');
    }

    public function testVerifyRejectsTamperedToken(): void
    {
        $issuer = Issuer::builder()->hsKey(self::SECRET)
            ->clock(fn() => 1_700_000_000)->build();
        $scope = $issuer->issue('u', ['tools']);
        $tampered = substr($scope->token, 0, -5) . 'XXXXX';

        $verifier = Verifier::builder()->hsKey(self::SECRET)
            ->clock(fn() => 1_700_000_001)->build();
        $this->expectException(InvalidTokenException::class);
        $verifier->verify($tampered);
    }

    public function testGenerateHs256SecretLength(): void
    {
        $s = Issuer::generateHs256Secret();
        self::assertGreaterThanOrEqual(64, strlen($s));
    }
}
