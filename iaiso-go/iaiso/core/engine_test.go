package core

import (
	"io"
	"log"
	"testing"

	"github.com/iaiso/iaiso-go/iaiso/audit"
)

func init() { WarnLogger = log.New(io.Discard, "", 0) }

func newEngine(t *testing.T, cfg PressureConfig, clock []float64, sink audit.Sink) *PressureEngine {
	t.Helper()
	e, err := NewPressureEngine(cfg, EngineOptions{
		ExecutionID:    "t",
		Sink:           sink,
		Clock:          ScriptedClock(clock),
		TimestampClock: func() float64 { return 0 },
	})
	if err != nil {
		t.Fatalf("construct: %v", err)
	}
	return e
}

func TestStepAccumulatesPressure(t *testing.T) {
	cfg := DefaultConfig()
	cfg.DissipationPerStep = 0
	e := newEngine(t, cfg, []float64{0, 0.1}, audit.NewMemorySink())
	if out := e.Step(StepInput{Tokens: 1000}); out != OutcomeOK {
		t.Fatalf("outcome = %v, want ok", out)
	}
	if got := e.Pressure(); got < 0.015-1e-9 || got > 0.015+1e-9 {
		t.Fatalf("pressure = %v, want 0.015", got)
	}
}

func TestEscalatedStillAcceptsSteps(t *testing.T) {
	// ESCALATED is a signal, not a stop. This is deliberate; regressing it
	// would silently turn a warning into an outage.
	cfg := DefaultConfig()
	cfg.EscalationThreshold, cfg.ReleaseThreshold = 0.5, 0.95
	cfg.DissipationPerStep, cfg.DepthCoefficient = 0, 0.6
	e := newEngine(t, cfg, []float64{0, 0.1, 0.2}, audit.NewMemorySink())

	if out := e.Step(StepInput{Depth: 1}); out != OutcomeEscalated {
		t.Fatalf("outcome = %v, want escalated", out)
	}
	if e.Lifecycle() != LifecycleEscalated {
		t.Fatalf("lifecycle = %v", e.Lifecycle())
	}
	if out := e.Step(StepInput{}); out == OutcomeLocked {
		t.Fatal("escalated engine rejected a step; only locked may reject")
	}
}

func TestReleaseLocksAndLockedRejects(t *testing.T) {
	cfg := DefaultConfig()
	cfg.EscalationThreshold, cfg.ReleaseThreshold = 0.5, 0.75
	cfg.DissipationPerStep, cfg.DepthCoefficient = 0, 0.8
	sink := audit.NewMemorySink()
	e := newEngine(t, cfg, []float64{0, 0.1, 0.2}, sink)

	if out := e.Step(StepInput{Depth: 1}); out != OutcomeReleased {
		t.Fatalf("outcome = %v, want released", out)
	}
	if e.Lifecycle() != LifecycleLocked || e.Pressure() != 0 {
		t.Fatalf("post-release state: %v %v", e.Lifecycle(), e.Pressure())
	}
	before := e.Snapshot()
	if out := e.Step(StepInput{Tokens: 999, ToolCalls: 999}); out != OutcomeLocked {
		t.Fatalf("outcome = %v, want locked", out)
	}
	after := e.Snapshot()
	if before.Step != after.Step {
		t.Fatalf("locked step mutated the counter: %d -> %d", before.Step, after.Step)
	}
	if !hasKind(sink, "engine.step.rejected") {
		t.Fatal("no engine.step.rejected emitted")
	}
}

func TestBackwardsClockCannotBuyDecay(t *testing.T) {
	cfg := DefaultConfig()
	cfg.DissipationPerStep, cfg.DissipationPerSecond = 0, 1.0
	cfg.TokenCoefficient, cfg.DepthCoefficient = 0, 0
	e := newEngine(t, cfg, []float64{10, 5}, audit.NewMemorySink())
	e.Step(StepInput{ToolCalls: 1})
	if got := e.Pressure(); got < 0.08-1e-9 || got > 0.08+1e-9 {
		t.Fatalf("pressure = %v, want 0.08 (elapsed clamped to 0)", got)
	}
}

func TestResetClearsLockedState(t *testing.T) {
	cfg := DefaultConfig()
	cfg.EscalationThreshold, cfg.ReleaseThreshold = 0.5, 0.75
	cfg.DissipationPerStep, cfg.DepthCoefficient = 0, 0.8
	e := newEngine(t, cfg, []float64{0, 0.1, 0.2}, audit.NewMemorySink())
	e.Step(StepInput{Depth: 1})
	snap := e.Reset()
	if snap.Lifecycle != LifecycleInit || snap.Step != 0 || snap.Pressure != 0 {
		t.Fatalf("reset left state %+v", snap)
	}
	if snap.LastStepAt != 0.2 {
		t.Fatalf("reset last_step_at = %v, want 0.2", snap.LastStepAt)
	}
}

func TestEmitDoesNotHoldStateLock(t *testing.T) {
	// A sink that reads engine state must not deadlock. Rust drops its lock
	// before emit for exactly this reason; Go must too.
	cfg := DefaultConfig()
	e, err := NewPressureEngine(cfg, EngineOptions{ExecutionID: "t", Clock: ScriptedClock([]float64{0, 1})})
	if err != nil {
		t.Fatal(err)
	}
	reentrant := sinkFunc(func(ev audit.Event) { _ = e.Pressure() })
	e2, err := NewPressureEngine(cfg, EngineOptions{
		ExecutionID: "t2", Sink: reentrant, Clock: ScriptedClock([]float64{0, 1}),
	})
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan struct{})
	go func() { e2.Step(StepInput{Tokens: 10}); close(done) }()
	<-done
}

type sinkFunc func(audit.Event)

func (f sinkFunc) Emit(ev audit.Event) { f(ev) }

func hasKind(s *audit.MemorySink, kind string) bool {
	for _, ev := range s.Events() {
		if ev.Kind == kind {
			return true
		}
	}
	return false
}

func TestConcurrentStepsAreSerialised(t *testing.T) {
	cfg := DefaultConfig()
	cfg.DissipationPerStep = 0
	e, err := NewPressureEngine(cfg, EngineOptions{ExecutionID: "t", Clock: Wallclock()})
	if err != nil {
		t.Fatal(err)
	}
	done := make(chan struct{})
	for i := 0; i < 8; i++ {
		go func() {
			for j := 0; j < 50; j++ {
				e.Step(StepInput{Tokens: 1})
			}
			done <- struct{}{}
		}()
	}
	for i := 0; i < 8; i++ {
		<-done
	}
	if got := e.Snapshot().Step; got != 400 {
		t.Fatalf("step counter = %d, want 400 (lost updates under concurrency)", got)
	}
}
