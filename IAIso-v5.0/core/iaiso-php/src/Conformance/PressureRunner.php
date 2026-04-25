<?php

declare(strict_types=1);

namespace IAIso\Conformance;

use IAIso\Audit\NullSink;
use IAIso\Core\ConfigException;
use IAIso\Core\EngineOptions;
use IAIso\Core\PressureConfig;
use IAIso\Core\PressureEngine;
use IAIso\Core\ScriptedClock;
use IAIso\Core\StepInput;

/** @internal */
final class PressureRunner
{
    public const TOLERANCE = 1e-9;

    private function __construct() {}

    /** @return VectorResult[] */
    public static function run(string $specRoot): array
    {
        $file = $specRoot . '/pressure/vectors.json';
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

        $expectErr = $v['expect_config_error'] ?? null;
        try {
            $engine = new PressureEngine($cfg, new EngineOptions(
                "vec-$name", NullSink::instance(), $clk, $clk));
        } catch (ConfigException $e) {
            if ($expectErr === null) {
                return VectorResult::fail('pressure', $name,
                    'engine construction failed: ' . $e->getMessage());
            }
            if (!str_contains($e->getMessage(), $expectErr)) {
                return VectorResult::fail('pressure', $name,
                    "expected error containing '$expectErr', got: " . $e->getMessage());
            }
            return VectorResult::pass('pressure', $name);
        }
        if ($expectErr !== null) {
            return VectorResult::fail('pressure', $name,
                "expected config error containing '$expectErr', got Ok");
        }

        if (isset($v['expected_initial']) && is_array($v['expected_initial'])) {
            $init = $v['expected_initial'];
            $snap = $engine->snapshot();
            if (abs($snap->pressure - (float) $init['pressure']) > self::TOLERANCE) {
                return VectorResult::fail('pressure', $name,
                    "initial pressure: got {$snap->pressure}, want {$init['pressure']}");
            }
            if ($snap->step !== (int) $init['step']) {
                return VectorResult::fail('pressure', $name,
                    "initial step: got {$snap->step}, want {$init['step']}");
            }
            if ($snap->lifecycle->value !== $init['lifecycle']) {
                return VectorResult::fail('pressure', $name,
                    "initial lifecycle: got {$snap->lifecycle->value}, want {$init['lifecycle']}");
            }
            if (abs($snap->lastStepAt - (float) $init['last_step_at']) > self::TOLERANCE) {
                return VectorResult::fail('pressure', $name,
                    "initial last_step_at: got {$snap->lastStepAt}, want {$init['last_step_at']}");
            }
        }

        $steps = $v['steps'] ?? [];
        $expSteps = $v['expected_steps'] ?? [];
        foreach ($steps as $i => $step) {
            if (isset($step['reset']) && $step['reset']) {
                $engine->reset();
                $outcome = 'ok';
            } else {
                $sib = StepInput::builder();
                if (isset($step['tokens']))     $sib->tokens((int) $step['tokens']);
                if (isset($step['tool_calls']))  $sib->toolCalls((int) $step['tool_calls']);
                if (isset($step['depth']))       $sib->depth((int) $step['depth']);
                if (isset($step['tag']) && $step['tag'] !== null) $sib->tag((string) $step['tag']);
                $outcome = $engine->step($sib->build())->value;
            }
            if (!isset($expSteps[$i])) {
                return VectorResult::fail('pressure', $name, "step $i: no expected entry");
            }
            $exp = $expSteps[$i];
            if ($outcome !== $exp['outcome']) {
                return VectorResult::fail('pressure', $name,
                    "step $i: outcome got $outcome, want {$exp['outcome']}");
            }
            $snap = $engine->snapshot();
            if (abs($snap->pressure - (float) $exp['pressure']) > self::TOLERANCE) {
                return VectorResult::fail('pressure', $name,
                    "step $i: pressure got {$snap->pressure}, want {$exp['pressure']}");
            }
            if ($snap->step !== (int) $exp['step']) {
                return VectorResult::fail('pressure', $name,
                    "step $i: step got {$snap->step}, want {$exp['step']}");
            }
            if ($snap->lifecycle->value !== $exp['lifecycle']) {
                return VectorResult::fail('pressure', $name,
                    "step $i: lifecycle got {$snap->lifecycle->value}, want {$exp['lifecycle']}");
            }
        }
        return VectorResult::pass('pressure', $name);
    }
}
