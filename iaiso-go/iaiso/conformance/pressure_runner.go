package conformance

import (
	"encoding/json"
	"strings"

	"github.com/iaiso/iaiso-go/iaiso/core"
)

type pressureStep struct {
	Tokens    uint64  `json:"tokens"`
	ToolCalls uint64  `json:"tool_calls"`
	Depth     uint64  `json:"depth"`
	Tag       *string `json:"tag"`
}

// Pointer fields distinguish "absent" from "zero": several vectors omit
// delta and decay on rejected steps, and asserting 0.0 there would be wrong.
type pressureExpectedStep struct {
	Step      *uint64  `json:"step"`
	Delta     *float64 `json:"delta"`
	Decay     *float64 `json:"decay"`
	Pressure  *float64 `json:"pressure"`
	Lifecycle *string  `json:"lifecycle"`
	Outcome   *string  `json:"outcome"`
}

type pressureExpectedState struct {
	Pressure   *float64 `json:"pressure"`
	Step       *uint64  `json:"step"`
	Lifecycle  *string  `json:"lifecycle"`
	LastStepAt *float64 `json:"last_step_at"`
}

type pressureVector struct {
	Name              string                 `json:"name"`
	Description       string                 `json:"description"`
	Config            map[string]any         `json:"config"`
	Clock             []float64              `json:"clock"`
	Steps             []pressureStep         `json:"steps"`
	ExpectedInitial   *pressureExpectedState `json:"expected_initial"`
	ExpectedSteps     []pressureExpectedStep `json:"expected_steps"`
	ResetAfterStep    *int                   `json:"reset_after_step"`
	ClockAfterReset   *float64               `json:"clock_after_reset"`
	ExpectedAfterRst  *pressureExpectedState `json:"expected_after_reset"`
	ExpectConfigError *string                `json:"expect_config_error"`
}

type pressureFile struct {
	Tolerance float64          `json:"tolerance"`
	Vectors   []pressureVector `json:"vectors"`
}

func configFromMap(m map[string]any) core.PressureConfig {
	cfg := core.DefaultConfig()
	getf := func(key string, dst *float64) {
		if v, ok := m[key]; ok {
			if f, ok := v.(float64); ok {
				*dst = f
			}
		}
	}
	getf("escalation_threshold", &cfg.EscalationThreshold)
	getf("release_threshold", &cfg.ReleaseThreshold)
	getf("dissipation_per_step", &cfg.DissipationPerStep)
	getf("dissipation_per_second", &cfg.DissipationPerSecond)
	getf("token_coefficient", &cfg.TokenCoefficient)
	getf("tool_coefficient", &cfg.ToolCoefficient)
	getf("depth_coefficient", &cfg.DepthCoefficient)
	if v, ok := m["post_release_lock"].(bool); ok {
		cfg.PostReleaseLock = v
	}
	return cfg
}

func runPressure(specRoot string) ([]Result, error) {
	raw, err := readVectors(specRoot, "pressure")
	if err != nil {
		return nil, err
	}
	var file pressureFile
	if err := json.Unmarshal(raw, &file); err != nil {
		return nil, err
	}
	if file.Tolerance == 0 {
		file.Tolerance = 1e-9
	}

	out := make([]Result, 0, len(file.Vectors))
	for _, v := range file.Vectors {
		out = append(out, runOnePressure(v, file.Tolerance))
	}
	return out, nil
}

func runOnePressure(v pressureVector, tol float64) Result {
	const section = "pressure"
	cfg := configFromMap(v.Config)

	// Vectors that assert on construction failure never build an engine.
	if v.ExpectConfigError != nil {
		_, err := core.NewPressureEngine(cfg, core.EngineOptions{
			ExecutionID: v.Name,
			Clock:       core.ScriptedClock(v.Clock),
		})
		if err == nil {
			return fail(section, v.Name, "expected config error containing %q, got nil", *v.ExpectConfigError)
		}
		if !strings.Contains(err.Error(), *v.ExpectConfigError) {
			return fail(section, v.Name, "expected config error containing %q, got %q",
				*v.ExpectConfigError, err.Error())
		}
		return pass(section, v.Name)
	}

	// The scripted clock drives engine state. Event timestamps get their own
	// clock so emission does not consume the vector's clock array.
	engine, err := core.NewPressureEngine(cfg, core.EngineOptions{
		ExecutionID:    v.Name,
		Clock:          core.ScriptedClock(v.Clock),
		TimestampClock: func() float64 { return 0 },
	})
	if err != nil {
		return fail(section, v.Name, "engine construction failed: %v", err)
	}

	if v.ExpectedInitial != nil {
		if msg := checkState(engine.Snapshot(), *v.ExpectedInitial, tol, "initial"); msg != "" {
			return fail(section, v.Name, "%s", msg)
		}
	}

	for i, step := range v.Steps {
		outcome := engine.Step(core.StepInput{
			Tokens: step.Tokens, ToolCalls: step.ToolCalls, Depth: step.Depth, Tag: step.Tag,
		})
		if i < len(v.ExpectedSteps) {
			if msg := checkStep(engine, outcome, v.ExpectedSteps[i], tol, i+1); msg != "" {
				return fail(section, v.Name, "%s", msg)
			}
		}
		if v.ResetAfterStep != nil && i+1 == *v.ResetAfterStep {
			engine.Reset()
		}
	}

	if v.ExpectedAfterRst != nil {
		if msg := checkState(engine.Snapshot(), *v.ExpectedAfterRst, tol, "after_reset"); msg != "" {
			return fail(section, v.Name, "%s", msg)
		}
	}
	return pass(section, v.Name)
}

func checkState(got core.Snapshot, want pressureExpectedState, tol float64, label string) string {
	if want.Pressure != nil && !floatClose(got.Pressure, *want.Pressure, tol) {
		return sprintf("%s pressure: got %v, want %v", label, got.Pressure, *want.Pressure)
	}
	if want.Step != nil && got.Step != *want.Step {
		return sprintf("%s step: got %d, want %d", label, got.Step, *want.Step)
	}
	if want.Lifecycle != nil && got.Lifecycle.String() != *want.Lifecycle {
		return sprintf("%s lifecycle: got %s, want %s", label, got.Lifecycle, *want.Lifecycle)
	}
	if want.LastStepAt != nil && !floatClose(got.LastStepAt, *want.LastStepAt, tol) {
		return sprintf("%s last_step_at: got %v, want %v", label, got.LastStepAt, *want.LastStepAt)
	}
	return ""
}

func checkStep(engine *core.PressureEngine, outcome core.StepOutcome,
	want pressureExpectedStep, tol float64, n int) string {

	snap := engine.Snapshot()
	if want.Outcome != nil && outcome.String() != *want.Outcome {
		return sprintf("step %d outcome: got %s, want %s", n, outcome, *want.Outcome)
	}
	if want.Step != nil && snap.Step != *want.Step {
		return sprintf("step %d counter: got %d, want %d", n, snap.Step, *want.Step)
	}
	if want.Pressure != nil && !floatClose(snap.Pressure, *want.Pressure, tol) {
		return sprintf("step %d pressure: got %v, want %v", n, snap.Pressure, *want.Pressure)
	}
	if want.Lifecycle != nil && snap.Lifecycle.String() != *want.Lifecycle {
		return sprintf("step %d lifecycle: got %s, want %s", n, snap.Lifecycle, *want.Lifecycle)
	}
	// delta and decay are only assertable via last_delta = delta - decay.
	if want.Delta != nil && want.Decay != nil {
		wantLast := *want.Delta - *want.Decay
		if !floatClose(snap.LastDelta, wantLast, tol) {
			return sprintf("step %d last_delta: got %v, want %v (delta %v - decay %v)",
				n, snap.LastDelta, wantLast, *want.Delta, *want.Decay)
		}
	}
	return ""
}
