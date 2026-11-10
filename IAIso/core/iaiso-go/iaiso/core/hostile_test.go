package core

import (
	"encoding/json"
	"math"
	"os"
	"path/filepath"
	"testing"

	"github.com/SmartTasksOrg/IAISO/IAIso/core/iaiso-go/iaiso/audit"
)

// spec/pressure/hostile.json is shared by every IAIso port.
type hostileFile struct {
	Reject []struct {
		Name  string          `json:"name"`
		Field string          `json:"field"`
		Value json.RawMessage `json:"value"`
		Class string          `json:"class"`
	} `json:"reject"`
	Accept []struct {
		Name   string            `json:"name"`
		Step   map[string]uint64 `json:"step"`
		Expect struct {
			Pressure  float64 `json:"pressure"`
			Outcome   string  `json:"outcome"`
			Lifecycle string  `json:"lifecycle"`
		} `json:"expect"`
	} `json:"accept"`
}

func loadHostile(t *testing.T) hostileFile {
	t.Helper()
	raw, err := os.ReadFile(filepath.Join("..", "..", "spec", "pressure", "hostile.json"))
	if err != nil {
		t.Fatalf("read hostile.json: %v", err)
	}
	var h hostileFile
	if err := json.Unmarshal(raw, &h); err != nil {
		t.Fatalf("parse hostile.json: %v", err)
	}
	return h
}

// DecodeStepInput is how untrusted JSON reaches the engine in Go: StepInput's
// counts are uint64, so negative, fractional, boolean and string values fail
// to decode. JSON null would silently decode to 0, so it is refused explicitly.
func TestHostileRejects(t *testing.T) {
	for _, v := range loadHostile(t).Reject {
		v := v
		t.Run(v.Name, func(t *testing.T) {
			_, err := DecodeStepInput([]byte(`{"` + v.Field + `":` + string(v.Value) + `}`))
			if err == nil {
				t.Fatalf("%s=%s was accepted", v.Field, v.Value)
			}
		})
	}
}

func TestHostileAccepts(t *testing.T) {
	for _, v := range loadHostile(t).Accept {
		v := v
		t.Run(v.Name, func(t *testing.T) {
			e := newEngine(t, DefaultConfig(), []float64{0, 0}, audit.NewMemorySink())
			out := e.Step(StepInput{Tokens: v.Step["tokens"], ToolCalls: v.Step["tool_calls"], Depth: v.Step["depth"]})
			p := e.Pressure()
			if math.IsNaN(p) || math.Abs(p-v.Expect.Pressure) > 1e-9 {
				t.Fatalf("pressure = %v, want %v", p, v.Expect.Pressure)
			}
			if string(out) != v.Expect.Outcome || string(e.Lifecycle()) != v.Expect.Lifecycle {
				t.Fatalf("outcome/lifecycle = %v/%v, want %v/%v", out, e.Lifecycle(), v.Expect.Outcome, v.Expect.Lifecycle)
			}
		})
	}
}

func TestDecodeStepInputAcceptsValid(t *testing.T) {
	w, err := DecodeStepInput([]byte(`{"tokens":10,"tool_calls":1,"depth":0,"tag":"x"}`))
	if err != nil || w.Tokens != 10 || w.ToolCalls != 1 || w.Tag == nil || *w.Tag != "x" {
		t.Fatalf("got %+v, %v", w, err)
	}
	if _, err := DecodeStepInput([]byte(`{"tokens":1,"unknown":2}`)); err == nil {
		t.Fatal("unknown field accepted")
	}
}
