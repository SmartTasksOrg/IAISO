<?php

declare(strict_types=1);

namespace IAIso\Conformance;

use IAIso\Policy\Policy;
use IAIso\Policy\PolicyException;
use IAIso\Policy\PolicyLoader;

/** @internal */
final class PolicyRunner
{
    public const TOLERANCE = 1e-9;

    private function __construct() {}

    /** @return VectorResult[] */
    public static function run(string $specRoot): array
    {
        $file = $specRoot . '/policy/vectors.json';
        $doc = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        $out = [];
        foreach ($doc['valid'] ?? [] as $v) {
            $out[] = self::runValid($v);
        }
        foreach ($doc['invalid'] ?? [] as $v) {
            $out[] = self::runInvalid($v);
        }
        return $out;
    }

    private static function runValid(array $v): VectorResult
    {
        $name = 'valid/' . $v['name'];
        try {
            $p = PolicyLoader::build($v['document']);

            if (isset($v['expected_pressure']) && is_array($v['expected_pressure'])) {
                $err = self::checkPressure($p, $v['expected_pressure']);
                if ($err !== null) return VectorResult::fail('policy', $name, $err);
            }
            if (isset($v['expected_consent']) && is_array($v['expected_consent'])) {
                $err = self::checkConsent($p, $v['expected_consent']);
                if ($err !== null) return VectorResult::fail('policy', $name, $err);
            }
            if (isset($v['expected_metadata']) && is_array($v['expected_metadata'])) {
                if (count($v['expected_metadata']) !== count($p->metadata)) {
                    return VectorResult::fail('policy', $name,
                        'metadata size: got ' . count($p->metadata)
                        . ', want ' . count($v['expected_metadata']));
                }
            }
            return VectorResult::pass('policy', $name);
        } catch (\Throwable $e) {
            return VectorResult::fail('policy', $name, 'build failed: ' . $e->getMessage());
        }
    }

    private static function checkPressure(Policy $p, array $ep): ?string
    {
        $checks = [
            ['token_coefficient', $p->pressure->tokenCoefficient],
            ['tool_coefficient', $p->pressure->toolCoefficient],
            ['depth_coefficient', $p->pressure->depthCoefficient],
            ['dissipation_per_step', $p->pressure->dissipationPerStep],
            ['dissipation_per_second', $p->pressure->dissipationPerSecond],
            ['escalation_threshold', $p->pressure->escalationThreshold],
            ['release_threshold', $p->pressure->releaseThreshold],
        ];
        foreach ($checks as [$k, $got]) {
            if (isset($ep[$k])) {
                $want = (float) $ep[$k];
                if (abs($got - $want) > self::TOLERANCE) {
                    return "$k: got $got, want $want";
                }
            }
        }
        if (isset($ep['post_release_lock'])) {
            $want = (bool) $ep['post_release_lock'];
            if ($want !== $p->pressure->postReleaseLock) {
                return 'post_release_lock mismatch';
            }
        }
        return null;
    }

    private static function checkConsent(Policy $p, array $ec): ?string
    {
        if (array_key_exists('issuer', $ec)) {
            $want = $ec['issuer'];
            if ($want !== $p->consent->issuer) {
                $g = $p->consent->issuer ?? 'null';
                $w = $want ?? 'null';
                return "consent.issuer: got $g, want $w";
            }
        }
        if (isset($ec['default_ttl_seconds'])) {
            $want = (float) $ec['default_ttl_seconds'];
            if (abs($p->consent->defaultTtlSeconds - $want) > self::TOLERANCE) {
                return "default_ttl_seconds: got {$p->consent->defaultTtlSeconds}, want $want";
            }
        }
        if (isset($ec['required_scopes'])) {
            if (count($ec['required_scopes']) !== count($p->consent->requiredScopes)) {
                return 'required_scopes length mismatch';
            }
        }
        if (isset($ec['allowed_algorithms'])) {
            if (count($ec['allowed_algorithms']) !== count($p->consent->allowedAlgorithms)) {
                return 'allowed_algorithms length mismatch';
            }
        }
        return null;
    }

    private static function runInvalid(array $v): VectorResult
    {
        $name = 'invalid/' . $v['name'];
        $expectPath = $v['expect_error_path'];
        try {
            PolicyLoader::build($v['document']);
            return VectorResult::fail('policy', $name,
                "expected error containing '$expectPath', got Ok");
        } catch (PolicyException $e) {
            if (!str_contains($e->getMessage(), $expectPath)) {
                return VectorResult::fail('policy', $name,
                    "expected error containing '$expectPath', got: " . $e->getMessage());
            }
            return VectorResult::pass('policy', $name);
        }
    }
}
