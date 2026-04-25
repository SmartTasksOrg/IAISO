<?php

declare(strict_types=1);

namespace IAIso\Policy;

use IAIso\Core\ConfigException;
use IAIso\Core\PressureConfig;

/**
 * IAIso policy loader. JSON-only — to keep the SDK dependency-light.
 * Convert YAML policies to JSON outside this SDK if needed.
 */
final class PolicyLoader
{
    private const SCOPE_PATTERN = '/^[a-z0-9_-]+(\.[a-z0-9_-]+)*$/';

    private function __construct() {}

    /** Validate a parsed JSON document against {@code spec/policy/README.md}. */
    public static function validate(mixed $doc): void
    {
        if (!is_array($doc) || array_is_list($doc)) {
            throw new PolicyException('$: policy document must be a mapping');
        }
        if (!array_key_exists('version', $doc)) {
            throw new PolicyException("\$: required property 'version' missing");
        }
        $v = $doc['version'];
        if (!is_string($v) || $v !== '1') {
            throw new PolicyException(
                '$.version: must be exactly "1", got ' . self::repr($v));
        }

        if (array_key_exists('pressure', $doc)) {
            $p = $doc['pressure'];
            if (!is_array($p) || array_is_list($p)) {
                throw new PolicyException('$.pressure: must be a mapping');
            }
            $nonNeg = ['token_coefficient', 'tool_coefficient', 'depth_coefficient',
                       'dissipation_per_step', 'dissipation_per_second'];
            foreach ($nonNeg as $f) {
                if (array_key_exists($f, $p)) {
                    if (!self::isNumber($p[$f])) {
                        throw new PolicyException("\$.pressure.$f: expected number");
                    }
                    if ($p[$f] < 0) {
                        throw new PolicyException(
                            "\$.pressure.$f: must be non-negative (got {$p[$f]})");
                    }
                }
            }
            foreach (['escalation_threshold', 'release_threshold'] as $f) {
                if (array_key_exists($f, $p)) {
                    if (!self::isNumber($p[$f])) {
                        throw new PolicyException("\$.pressure.$f: expected number");
                    }
                    $n = $p[$f];
                    if ($n < 0 || $n > 1) {
                        throw new PolicyException(
                            "\$.pressure.$f: must be in [0, 1] (got $n)");
                    }
                }
            }
            if (array_key_exists('post_release_lock', $p)
                    && !is_bool($p['post_release_lock'])) {
                throw new PolicyException('$.pressure.post_release_lock: expected boolean');
            }
            $esc = $p['escalation_threshold'] ?? null;
            $rel = $p['release_threshold'] ?? null;
            if (self::isNumber($esc) && self::isNumber($rel) && $rel <= $esc) {
                throw new PolicyException(
                    "\$.pressure.release_threshold: must exceed escalation_threshold ($rel <= $esc)");
            }
        }

        if (array_key_exists('coordinator', $doc)) {
            $c = $doc['coordinator'];
            if (!is_array($c) || array_is_list($c)) {
                throw new PolicyException('$.coordinator: must be a mapping');
            }
            if (array_key_exists('aggregator', $c)) {
                $name = $c['aggregator'];
                if (!is_string($name) || !in_array($name, ['sum', 'mean', 'max', 'weighted_sum'], true)) {
                    throw new PolicyException(
                        '$.coordinator.aggregator: must be one of sum|mean|max|weighted_sum (got '
                        . self::repr($name) . ')');
                }
            }
            $esc = $c['escalation_threshold'] ?? null;
            $rel = $c['release_threshold'] ?? null;
            if (self::isNumber($esc) && self::isNumber($rel) && $rel <= $esc) {
                throw new PolicyException(
                    "\$.coordinator.release_threshold: must exceed escalation_threshold ($rel <= $esc)");
            }
        }

        if (array_key_exists('consent', $doc)) {
            $c = $doc['consent'];
            if (!is_array($c) || array_is_list($c)) {
                throw new PolicyException('$.consent: must be a mapping');
            }
            if (array_key_exists('required_scopes', $c)) {
                $scopes = $c['required_scopes'];
                if (!is_array($scopes) || !array_is_list($scopes)) {
                    throw new PolicyException('$.consent.required_scopes: expected list');
                }
                foreach ($scopes as $i => $s) {
                    if (!is_string($s) || preg_match(self::SCOPE_PATTERN, $s) !== 1) {
                        throw new PolicyException(
                            "\$.consent.required_scopes[$i]: " . self::repr($s)
                            . ' is not a valid scope');
                    }
                }
            }
        }
    }

    /** Build a {@see Policy} from a parsed JSON document. */
    public static function build(mixed $doc): Policy
    {
        self::validate($doc);
        /** @var array<string,mixed> $doc */

        $pcb = PressureConfig::builder();
        if (array_key_exists('pressure', $doc) && is_array($doc['pressure'])) {
            $p = $doc['pressure'];
            self::applyDouble($p, 'escalation_threshold', fn($v) => $pcb->escalationThreshold($v));
            self::applyDouble($p, 'release_threshold', fn($v) => $pcb->releaseThreshold($v));
            self::applyDouble($p, 'dissipation_per_step', fn($v) => $pcb->dissipationPerStep($v));
            self::applyDouble($p, 'dissipation_per_second', fn($v) => $pcb->dissipationPerSecond($v));
            self::applyDouble($p, 'token_coefficient', fn($v) => $pcb->tokenCoefficient($v));
            self::applyDouble($p, 'tool_coefficient', fn($v) => $pcb->toolCoefficient($v));
            self::applyDouble($p, 'depth_coefficient', fn($v) => $pcb->depthCoefficient($v));
            if (array_key_exists('post_release_lock', $p) && is_bool($p['post_release_lock'])) {
                $pcb->postReleaseLock($p['post_release_lock']);
            }
        }
        $pressure = $pcb->build();
        try {
            $pressure->validate();
        } catch (ConfigException $e) {
            throw new PolicyException('$.pressure: ' . $e->getMessage(), 0, $e);
        }

        $coord = CoordinatorConfig::defaults();
        $aggregator = new SumAggregator();
        if (array_key_exists('coordinator', $doc) && is_array($doc['coordinator'])) {
            $c = $doc['coordinator'];
            $escThr = self::numericOr($c, 'escalation_threshold', $coord->escalationThreshold);
            $relThr = self::numericOr($c, 'release_threshold', $coord->releaseThreshold);
            $cooldown = self::numericOr($c, 'notify_cooldown_seconds', $coord->notifyCooldownSeconds);
            $coord = new CoordinatorConfig($escThr, $relThr, $cooldown);
            $aggregator = self::buildAggregator($c);
        }

        $consent = ConsentPolicy::defaults();
        if (array_key_exists('consent', $doc) && is_array($doc['consent'])) {
            $c = $doc['consent'];
            $issuer = isset($c['issuer']) && is_string($c['issuer']) ? $c['issuer'] : null;
            $ttl = self::numericOr($c, 'default_ttl_seconds', $consent->defaultTtlSeconds);
            $required = $consent->requiredScopes;
            if (isset($c['required_scopes']) && is_array($c['required_scopes'])) {
                $required = array_values(array_map('strval', $c['required_scopes']));
            }
            $algos = $consent->allowedAlgorithms;
            if (isset($c['allowed_algorithms']) && is_array($c['allowed_algorithms'])) {
                $algos = array_values(array_map('strval', $c['allowed_algorithms']));
            }
            $consent = new ConsentPolicy($issuer, $ttl, $required, $algos);
        }

        $metadata = [];
        if (array_key_exists('metadata', $doc) && is_array($doc['metadata'])
                && !array_is_list($doc['metadata'])) {
            $metadata = $doc['metadata'];
        }

        return new Policy('1', $pressure, $coord, $consent, $aggregator, $metadata);
    }

    /** Parse JSON-encoded policy bytes. */
    public static function parseJson(string $data): Policy
    {
        try {
            $doc = json_decode($data, true, 512, JSON_THROW_ON_ERROR);
        } catch (\JsonException $e) {
            throw new PolicyException('policy JSON parse failed: ' . $e->getMessage(), 0, $e);
        }
        return self::build($doc);
    }

    /** Load a policy from a file (.json only). */
    public static function load(string $path): Policy
    {
        if (!str_ends_with(strtolower($path), '.json')) {
            throw new PolicyException(
                "unsupported policy file extension: $path (only .json is supported in the PHP SDK)");
        }
        $data = @file_get_contents($path);
        if ($data === false) {
            throw new PolicyException("failed to read $path");
        }
        return self::parseJson($data);
    }

    private static function buildAggregator(array $coord): Aggregator
    {
        $name = $coord['aggregator'] ?? 'sum';
        switch ($name) {
            case 'mean':         return new MeanAggregator();
            case 'max':          return new MaxAggregator();
            case 'weighted_sum':
                $weights = [];
                if (isset($coord['weights']) && is_array($coord['weights'])
                        && !array_is_list($coord['weights'])) {
                    foreach ($coord['weights'] as $k => $v) {
                        if (self::isNumber($v)) {
                            $weights[(string) $k] = (float) $v;
                        }
                    }
                }
                $dw = self::numericOr($coord, 'default_weight', 1.0);
                return new WeightedSumAggregator($weights, $dw);
            default:
                return new SumAggregator();
        }
    }

    private static function isNumber(mixed $v): bool
    {
        return is_int($v) || is_float($v);
    }

    private static function numericOr(array $arr, string $key, float $fallback): float
    {
        if (array_key_exists($key, $arr) && self::isNumber($arr[$key])) {
            return (float) $arr[$key];
        }
        return $fallback;
    }

    private static function applyDouble(array $arr, string $key, callable $setter): void
    {
        if (array_key_exists($key, $arr) && self::isNumber($arr[$key])) {
            $setter((float) $arr[$key]);
        }
    }

    private static function repr(mixed $v): string
    {
        try {
            return json_encode($v, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE)
                ?: '<unencodable>';
        } catch (\Throwable) {
            return '<unencodable>';
        }
    }
}
