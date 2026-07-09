package core

import (
	"testing"

	"github.com/iaiso/iaiso-go/iaiso/audit"
)

func costConfig() PressureConfig {
	cfg := DefaultConfig()
	cfg.DissipationPerStep = 0
	cfg.ModelCosts = map[string]float64{"frontier": 15.0} // USD per 1M tokens
	return cfg
}

func TestSpendIsTrackedAndReported(t *testing.T) {
	sink := audit.NewMemorySink()
	e := newEngine(t, costConfig(), []float64{0, 1, 2}, sink)
	e.Step(StepInput{Tokens: 100_000, Model: "frontier"})

	if got := e.SpendUSD(); got < 1.5-1e-9 || got > 1.5+1e-9 {
		t.Fatalf("spend = %v, want 1.5", got)
	}
	for _, ev := range sink.Events() {
		if ev.Kind != "engine.step" {
			continue
		}
		if _, ok := ev.Data["spend_usd"]; !ok {
			t.Fatal("engine.step is missing spend_usd when model_costs is configured")
		}
	}
}

func TestSpendFieldAbsentWithoutModelCosts(t *testing.T) {
	// The event schema addition must be optional: existing consumers on the
	// 1.0 envelope must not see a new key appear.
	sink := audit.NewMemorySink()
	cfg := DefaultConfig()
	cfg.DissipationPerStep = 0
	e := newEngine(t, cfg, []float64{0, 1}, sink)
	e.Step(StepInput{Tokens: 1000})
	for _, ev := range sink.Events() {
		if ev.Kind == "engine.step" {
			if _, ok := ev.Data["spend_usd"]; ok {
				t.Fatal("spend_usd leaked into an event with no model_costs configured")
			}
		}
	}
}

func TestBudgetExceededTakesTheLockPath(t *testing.T) {
	cfg := costConfig()
	cfg.BudgetUSD = 1.0
	sink := audit.NewMemorySink()
	e := newEngine(t, cfg, []float64{0, 1, 2}, sink)

	if out := e.Step(StepInput{Tokens: 100_000, Model: "frontier"}); out != OutcomeLocked {
		t.Fatalf("outcome = %v, want locked (spend 1.5 >= budget 1.0)", out)
	}
	if e.Lifecycle() != LifecycleLocked {
		t.Fatalf("lifecycle = %v, want locked", e.Lifecycle())
	}
	// No new lifecycle state: the wire format is frozen.
	found := false
	for _, ev := range sink.Events() {
		if ev.Kind == "engine.locked" && ev.Data["reason"] == "budget_exceeded" {
			found = true
		}
	}
	if !found {
		t.Fatal("no engine.locked{reason:budget_exceeded} emitted")
	}
	if out := e.Step(StepInput{Tokens: 1}); out != OutcomeLocked {
		t.Fatal("budget-locked engine accepted a further step")
	}
}

func TestUnknownModelCostsNothing(t *testing.T) {
	e := newEngine(t, costConfig(), []float64{0, 1}, audit.NewMemorySink())
	e.Step(StepInput{Tokens: 1_000_000, Model: "unpriced"})
	if got := e.SpendUSD(); got != 0 {
		t.Fatalf("spend = %v, want 0 for an unpriced model", got)
	}
}
