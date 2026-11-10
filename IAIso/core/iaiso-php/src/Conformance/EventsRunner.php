<?php

declare(strict_types=1);

namespace IAIso\Conformance;

use IAIso\Audit\MemorySink;
use IAIso\Core\EngineOptions;
use IAIso\Core\PressureConfig;
use IAIso\Core\PressureEngine;
use IAIso\Core\ScriptedClock;
use IAIso\Core\StepInput;

/** @internal */
final class EventsRunner
{
    public const TOLERANCE = 1e-9;

    private function __construct() {}

    /** @return VectorResult[] */
    public static function run(string $specRoot): array
    {
        $file = $specRoot . '/events/vectors.json';
        $doc = json_decode((string) file_get_contents($file), true, 512, JSON_THROW_ON_ERROR);
        $out = [];
        foreach ($doc['vectors'] as $v) {
            $out[] = self::runOne($v);
        }
        return $out;
    }

    private static function runOne(array $v): VectorResult
    {
        $name = $v['name'];
        $cb = PressureConfig::builder();
        if (isset($v['config']) && is_array($v['config'])) {
            $c = $v['config'];
            foreach ([
                'escalation_threshold' => 'escalationThreshold',
                'release_threshold'    => 'releaseThreshold',
                'dissipation_per_step' => 'dissipationPerStep',
                'dissipation_per_second' => 'dissipationPerSecond',
                'token_coefficient'    => 'tokenCoefficient',
                'tool_coefficient'     => 'toolCoefficient',
                'depth_coefficient'    => 'depthCoefficient',
            ] as $k => $m) {
                if (isset($c[$k])) $cb->$m((float) $c[$k]);
            }
            if (isset($c['post_release_lock'])) $cb->postReleaseLock((bool) $c['post_release_lock']);
        }
        $cfg = $cb->build();

        $clockSeq = isset($v['clock']) && is_array($v['clock'])
            ? array_map('floatval', $v['clock']) : [0.0];
        $clk = new ScriptedClock($clockSeq);

        $sink = new MemorySink();
        $execId = $v['execution_id'];
        try {
            $engine = new PressureEngine($cfg,
                new EngineOptions($execId, $sink, $clk, $clk));
        } catch (\Throwable $e) {
            return VectorResult::fail('events', $name, 'engine init failed: ' . $e->getMessage());
        }

        $resetAfterStep = $v['reset_after_step'] ?? null;
        $steps = $v['steps'] ?? [];
        foreach ($steps as $i => $step) {
            if (isset($step['reset']) && $step['reset']) {
                $engine->reset();
            } else {
                $sib = StepInput::builder();
                if (isset($step['tokens']))     $sib->tokens((int) $step['tokens']);
                if (isset($step['tool_calls']))  $sib->toolCalls((int) $step['tool_calls']);
                if (isset($step['depth']))       $sib->depth((int) $step['depth']);
                if (isset($step['tag']) && $step['tag'] !== null) $sib->tag((string) $step['tag']);
                $engine->step($sib->build());
            }
            // 1-based: reset_after_step = N triggers after running step N
            if ($resetAfterStep !== null && ($i + 1) === (int) $resetAfterStep) {
                $engine->reset();
            }
        }

        $got = $sink->events();
        $expected = $v['expected_events'];
        if (count($got) !== count($expected)) {
            return VectorResult::fail('events', $name,
                'event count: got ' . count($got) . ', want ' . count($expected));
        }
        foreach ($expected as $i => $exp) {
            $actual = $got[$i];
            if (isset($exp['schema_version']) && $exp['schema_version'] !== '') {
                if ($exp['schema_version'] !== $actual->schemaVersion) {
                    return VectorResult::fail('events', $name,
                        "event $i schema_version: got {$actual->schemaVersion}, want {$exp['schema_version']}");
                }
            }
            if (isset($exp['execution_id']) && $exp['execution_id'] !== '') {
                if ($exp['execution_id'] !== $actual->executionId) {
                    return VectorResult::fail('events', $name,
                        "event $i execution_id: got {$actual->executionId}, want {$exp['execution_id']}");
                }
            }
            if ($exp['kind'] !== $actual->kind) {
                return VectorResult::fail('events', $name,
                    "event $i kind: got {$actual->kind}, want {$exp['kind']}");
            }
            if (isset($exp['data']) && is_array($exp['data'])) {
                if (!self::dataMatches($actual->data, $exp['data'])) {
                    $gotJson = json_encode($actual->data);
                    $wantJson = json_encode($exp['data']);
                    return VectorResult::fail('events', $name,
                        "event $i data mismatch: got $gotJson, want $wantJson");
                }
            }
        }
        return VectorResult::pass('events', $name);
    }

    /** Loose equality: keys missing in $actual treated as null; numbers compared with tolerance. */
    private static function dataMatches(array $actual, array $want): bool
    {
        foreach ($want as $k => $v) {
            $got = $actual[$k] ?? null;
            if (!self::valueEqual($got, $v)) return false;
        }
        return true;
    }

    private static function valueEqual(mixed $actual, mixed $want): bool
    {
        if ($want === null) return $actual === null;
        if ($actual === null) return false;
        if (is_bool($want)) return is_bool($actual) && $actual === $want;
        if (is_int($want) || is_float($want)) {
            if (!is_int($actual) && !is_float($actual)) return false;
            return abs((float) $actual - (float) $want) <= self::TOLERANCE;
        }
        if (is_string($want)) return is_string($actual) && $actual === $want;
        if (is_array($want)) {
            if (!is_array($actual)) return false;
            // List vs map
            if (array_is_list($want)) {
                if (!array_is_list($actual) || count($actual) !== count($want)) return false;
                foreach ($want as $i => $w) {
                    if (!self::valueEqual($actual[$i], $w)) return false;
                }
                return true;
            }
            foreach ($want as $k => $w) {
                if (!self::valueEqual($actual[$k] ?? null, $w)) return false;
            }
            return true;
        }
        return false;
    }
}
