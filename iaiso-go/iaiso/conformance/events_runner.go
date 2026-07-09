package conformance

import (
	"encoding/json"

	"github.com/iaiso/iaiso-go/iaiso/audit"
	"github.com/iaiso/iaiso-go/iaiso/core"
)

type eventsStep struct {
	Tokens    uint64  `json:"tokens"`
	ToolCalls uint64  `json:"tool_calls"`
	Depth     uint64  `json:"depth"`
	Tag       *string `json:"tag"`
}

type expectedEvent struct {
	SchemaVersion string         `json:"schema_version"`
	ExecutionID   string         `json:"execution_id"`
	Kind          string         `json:"kind"`
	Data          map[string]any `json:"data"`
}

type eventsVector struct {
	Name            string          `json:"name"`
	Description     string          `json:"description"`
	Config          map[string]any  `json:"config"`
	Clock           []float64       `json:"clock"`
	Steps           []eventsStep    `json:"steps"`
	ResetAfterStep  *int            `json:"reset_after_step"`
	ClockAfterReset *float64        `json:"clock_after_reset"`
	ExecutionID     string          `json:"execution_id"`
	ExpectedEvents  []expectedEvent `json:"expected_events"`
}

type eventsFile struct {
	Tolerance float64        `json:"tolerance"`
	Vectors   []eventsVector `json:"vectors"`
}

func runEvents(specRoot string) ([]Result, error) {
	raw, err := readVectors(specRoot, "events")
	if err != nil {
		return nil, err
	}
	var file eventsFile
	if err := json.Unmarshal(raw, &file); err != nil {
		return nil, err
	}
	if file.Tolerance == 0 {
		file.Tolerance = 1e-9
	}
	out := make([]Result, 0, len(file.Vectors))
	for _, v := range file.Vectors {
		out = append(out, runOneEvents(v, file.Tolerance))
	}
	return out, nil
}

func runOneEvents(v eventsVector, tol float64) Result {
	const section = "events"
	sink := audit.NewMemorySink()

	engine, err := core.NewPressureEngine(configFromMap(v.Config), core.EngineOptions{
		ExecutionID:    v.ExecutionID,
		Sink:           sink,
		Clock:          core.ScriptedClock(v.Clock),
		TimestampClock: func() float64 { return 0 },
	})
	if err != nil {
		return fail(section, v.Name, "engine construction failed: %v", err)
	}

	for i, step := range v.Steps {
		engine.Step(core.StepInput{
			Tokens: step.Tokens, ToolCalls: step.ToolCalls, Depth: step.Depth, Tag: step.Tag,
		})
		if v.ResetAfterStep != nil && i+1 == *v.ResetAfterStep {
			engine.Reset()
		}
	}

	got := sink.Events()
	if len(got) != len(v.ExpectedEvents) {
		return fail(section, v.Name, "event count: got %d (%v), want %d",
			len(got), kinds(got), len(v.ExpectedEvents))
	}

	for i, want := range v.ExpectedEvents {
		actual := got[i]
		if actual.Kind != want.Kind {
			return fail(section, v.Name, "event %d kind: got %q, want %q", i, actual.Kind, want.Kind)
		}
		if want.SchemaVersion != "" && actual.SchemaVersion != want.SchemaVersion {
			return fail(section, v.Name, "event %d schema_version: got %q, want %q",
				i, actual.SchemaVersion, want.SchemaVersion)
		}
		if want.ExecutionID != "" && actual.ExecutionID != want.ExecutionID {
			return fail(section, v.Name, "event %d execution_id: got %q, want %q",
				i, actual.ExecutionID, want.ExecutionID)
		}
		// Only the keys the vector names are asserted, so a port may add
		// optional fields (e.g. spend_usd) without breaking the suite.
		for key, wantVal := range want.Data {
			gotVal, present := actual.Data[key]
			if !present {
				return fail(section, v.Name, "event %d (%s) missing data key %q", i, want.Kind, key)
			}
			if !dataEqual(gotVal, wantVal, tol) {
				return fail(section, v.Name, "event %d (%s) data.%s: got %v, want %v",
					i, want.Kind, key, gotVal, wantVal)
			}
		}
	}
	return pass(section, v.Name)
}

func kinds(evs []audit.Event) []string {
	out := make([]string, len(evs))
	for i, e := range evs {
		out[i] = e.Kind
	}
	return out
}

// dataEqual compares an emitted value against a JSON-decoded expectation.
// Emitted numbers are Go native types; expectations are always float64.
func dataEqual(got, want any, tol float64) bool {
	if want == nil {
		return got == nil
	}
	if wf, ok := want.(float64); ok {
		gf, ok := numeric(got)
		return ok && floatClose(gf, wf, tol)
	}
	if ws, ok := want.(string); ok {
		gs, ok := got.(string)
		return ok && gs == ws
	}
	if wb, ok := want.(bool); ok {
		gb, ok := got.(bool)
		return ok && gb == wb
	}
	return false
}

func numeric(v any) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	case uint64:
		return float64(n), true
	case uint:
		return float64(n), true
	}
	return 0, false
}
