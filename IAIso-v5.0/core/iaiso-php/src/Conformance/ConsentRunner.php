<?php

declare(strict_types=1);

namespace IAIso\Conformance;

use IAIso\Consent\Algorithm;
use IAIso\Consent\ExpiredTokenException;
use IAIso\Consent\InvalidTokenException;
use IAIso\Consent\Issuer;
use IAIso\Consent\RevokedTokenException;
use IAIso\Consent\Scopes;
use IAIso\Consent\Verifier;

/** @internal */
final class ConsentRunner
{
    private function __construct() {}

    /** @return VectorResult[] */
    public static function run(string $specRoot): array
    {
        $file = $specRoot . '/consent/vectors.json';
        $doc = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        $sharedKey = $doc['hs256_key_shared'];

        $out = [];
        foreach ($doc['scope_match'] ?? [] as $v) {
            $out[] = self::runScopeMatch($v);
        }
        foreach ($doc['scope_match_errors'] ?? [] as $v) {
            $out[] = self::runScopeMatchError($v);
        }
        foreach ($doc['valid_tokens'] ?? [] as $v) {
            $out[] = self::runValidToken($sharedKey, $v);
        }
        foreach ($doc['invalid_tokens'] ?? [] as $v) {
            $out[] = self::runInvalidToken($sharedKey, $v);
        }
        foreach ($doc['issue_and_verify_roundtrip'] ?? [] as $v) {
            $out[] = self::runRoundtrip($sharedKey, $v);
        }
        return $out;
    }

    private static function runScopeMatch(array $v): VectorResult
    {
        $name = 'scope_match/' . $v['name'];
        try {
            $got = Scopes::granted($v['granted'], $v['requested']);
            $want = (bool) $v['expected'];
            if ($got !== $want) {
                return VectorResult::fail('consent', $name,
                    'got ' . ($got ? 'true' : 'false')
                    . ', want ' . ($want ? 'true' : 'false'));
            }
            return VectorResult::pass('consent', $name);
        } catch (\Throwable $e) {
            return VectorResult::fail('consent', $name,
                'unexpected exception: ' . $e->getMessage());
        }
    }

    private static function runScopeMatchError(array $v): VectorResult
    {
        $name = 'scope_match_errors/' . $v['name'];
        $expectErr = $v['expect_error'];
        try {
            Scopes::granted($v['granted'], $v['requested']);
            return VectorResult::fail('consent', $name,
                "expected error containing '$expectErr', got Ok");
        } catch (\InvalidArgumentException $e) {
            if (!str_contains(strtolower($e->getMessage()), strtolower($expectErr))) {
                return VectorResult::fail('consent', $name,
                    "expected '$expectErr', got: " . $e->getMessage());
            }
            return VectorResult::pass('consent', $name);
        }
    }

    private static function parseAlg(array $v): Algorithm
    {
        if (isset($v['algorithm'])) {
            return Algorithm::from($v['algorithm']);
        }
        return Algorithm::HS256;
    }

    private static function runValidToken(string $sharedKey, array $v): VectorResult
    {
        $name = 'valid_tokens/' . $v['name'];
        $now = (int) $v['now'];
        $issuer = $v['issuer'] ?? 'iaiso';
        $alg = self::parseAlg($v);

        $verifier = Verifier::builder()
            ->hsKey($sharedKey)->algorithm($alg)->issuer($issuer)
            ->clock(fn() => $now)->build();
        try {
            $s = $verifier->verify($v['token']);
            $exp = $v['expected'];
            if ($s->subject !== $exp['sub']) {
                return VectorResult::fail('consent', $name,
                    "sub: got {$s->subject}, want {$exp['sub']}");
            }
            if ($s->jti !== $exp['jti']) {
                return VectorResult::fail('consent', $name,
                    "jti: got {$s->jti}, want {$exp['jti']}");
            }
            $wantScopes = $exp['scopes'];
            if ($s->scopes !== $wantScopes) {
                return VectorResult::fail('consent', $name, 'scopes mismatch');
            }
            $wantExec = $exp['execution_id'] ?? null;
            if ($s->executionId !== $wantExec) {
                $g = $s->executionId ?? 'null';
                $w = $wantExec ?? 'null';
                return VectorResult::fail('consent', $name,
                    "execution_id: got $g, want $w");
            }
            return VectorResult::pass('consent', $name);
        } catch (\Throwable $e) {
            return VectorResult::fail('consent', $name, 'verify failed: ' . $e->getMessage());
        }
    }

    private static function runInvalidToken(string $sharedKey, array $v): VectorResult
    {
        $name = 'invalid_tokens/' . $v['name'];
        $now = (int) $v['now'];
        $issuer = $v['issuer'] ?? 'iaiso';
        $alg = self::parseAlg($v);
        $execId = $v['execution_id'] ?? null;
        $expectErr = $v['expect_error'];

        $verifier = Verifier::builder()
            ->hsKey($sharedKey)->algorithm($alg)->issuer($issuer)
            ->clock(fn() => $now)->build();
        try {
            $verifier->verify($v['token'], $execId);
            return VectorResult::fail('consent', $name,
                "expected error '$expectErr', got Ok");
        } catch (ExpiredTokenException) {
            if ($expectErr !== 'expired') {
                return VectorResult::fail('consent', $name, "expected '$expectErr', got expired");
            }
            return VectorResult::pass('consent', $name);
        } catch (RevokedTokenException) {
            if ($expectErr !== 'revoked') {
                return VectorResult::fail('consent', $name, "expected '$expectErr', got revoked");
            }
            return VectorResult::pass('consent', $name);
        } catch (InvalidTokenException $e) {
            if ($expectErr !== 'invalid') {
                return VectorResult::fail('consent', $name,
                    "expected '$expectErr', got invalid: " . $e->getMessage());
            }
            return VectorResult::pass('consent', $name);
        } catch (\Throwable $e) {
            return VectorResult::fail('consent', $name,
                'unexpected exception type: ' . get_class($e) . ': ' . $e->getMessage());
        }
    }

    private static function runRoundtrip(string $sharedKey, array $v): VectorResult
    {
        $name = 'roundtrip/' . $v['name'];
        $issueSpec = $v['issue'];
        $ttl = (int) ($issueSpec['ttl_seconds'] ?? 3600);
        $subject = $issueSpec['subject'];
        $scopes = $issueSpec['scopes'];
        $execId = $issueSpec['execution_id'] ?? null;
        $metadata = $issueSpec['metadata'] ?? null;
        $now = (int) ($v['now'] ?? 1700000000);
        $issuer = $v['issuer'] ?? 'iaiso';
        $alg = self::parseAlg($v);

        $is = Issuer::builder()->hsKey($sharedKey)->algorithm($alg)
            ->issuer($issuer)->clock(fn() => $now)->build();
        try {
            $scope = $is->issue($subject, $scopes, $execId, $ttl, $metadata);
        } catch (\Throwable $e) {
            return VectorResult::fail('consent', $name, 'issue failed: ' . $e->getMessage());
        }

        $expectSuccess = (bool) ($v['expected_after_verify_succeeds'] ?? false);
        $verifyExec = $v['verify_with_execution_id'] ?? null;

        $ver = Verifier::builder()->hsKey($sharedKey)->algorithm($alg)
            ->issuer($issuer)->clock(fn() => $now + 1)->build();
        try {
            $verified = $ver->verify($scope->token, $verifyExec);
            if (!$expectSuccess) {
                return VectorResult::fail('consent', $name, 'expected verify to fail, succeeded');
            }
            if ($verified->subject !== $subject) {
                return VectorResult::fail('consent', $name, 'subject mismatch');
            }
            if ($verified->scopes !== $scopes) {
                return VectorResult::fail('consent', $name, 'scopes mismatch');
            }
            return VectorResult::pass('consent', $name);
        } catch (\Throwable $e) {
            if ($expectSuccess) {
                return VectorResult::fail('consent', $name,
                    'expected verify to succeed, failed: ' . $e->getMessage());
            }
            return VectorResult::pass('consent', $name);
        }
    }
}
