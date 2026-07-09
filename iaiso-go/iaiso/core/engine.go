package core

import (
	"sync"

	"github.com/iaiso/iaiso-go/iaiso/audit"
)

// StepInput is the unit of work accounted for by a single Step call.
type StepInput struct {
	Tokens    uint64
	ToolCalls uint64
	Depth     uint64
	// Tag is optional. When unset it serialises as JSON null.
	Tag *string
	// Model selects a ModelCosts entry for spend accounting. Ignored when
	// PressureConfig.ModelCosts is empty.
	Model string
}

// Snapshot is a read-only view of engine state.
type Snapshot struct {
	Pressure   float64
	Step       uint64
	Lifecycle  Lifecycle
	LastDelta  float64
	LastStepAt float64
	SpendUSD   float64
}

// EngineOptions configures a PressureEngine.
type EngineOptions struct {
	ExecutionID string
	// Sink receives audit events. Defaults to audit.NullSink.
	Sink audit.Sink
	// Clock drives elapsed-time decay. Defaults to Wallclock.
	Clock Clock
	// TimestampClock stamps audit events. Defaults to Wallclock. It is
	// separate from Clock so a scripted state clock is not consumed by
	// event emission.
	TimestampClock Clock
	// EnforcementMode is "permissive" (default) or "strict". See BootGuard.
	EnforcementMode string
	// CalibrationArtifact, when non-empty, tells strict mode that the
	// coefficients were derived from a calibration run.
	CalibrationArtifact string
}

type engineState struct {
	pressure   float64
	step       uint64
	lifecycle  Lifecycle
	lastDelta  float64
	lastStepAt float64
	spendUSD   float64
}

// PressureEngine accumulates a single scalar — pressure — that rises with
// tokens, tool calls and planning depth and decays with steps and elapsed
// time. It escalates at one threshold and releases (and optionally locks)
// at a higher one.
//
// One number catches tool-loop runaways, token floods and planning spirals
// that three separate counters miss.
//
// Safe for concurrent use. The state mutex is never held while emitting an
// audit event: a sink that calls back into the engine would otherwise
// deadlock.
type PressureEngine struct {
	cfg            PressureConfig
	executionID    string
	sink           audit.Sink
	clock          Clock
	timestampClock Clock

	mu    sync.Mutex
	state engineState
}

// NewPressureEngine validates cfg, applies the enforcement_mode boot guard,
// records the initial clock reading and emits engine.init.
func NewPressureEngine(cfg PressureConfig, opts EngineOptions) (*PressureEngine, error) {
	if err := cfg.Validate(); err != nil {
		return nil, err
	}
	if opts.Sink == nil {
		opts.Sink = audit.NewNullSink()
	}
	if opts.Clock == nil {
		opts.Clock = Wallclock()
	}
	if opts.TimestampClock == nil {
		opts.TimestampClock = Wallclock()
	}
	if err := BootGuard(cfg, opts); err != nil {
		return nil, err
	}

	now := opts.Clock()
	e := &PressureEngine{
		cfg:            cfg,
		executionID:    opts.ExecutionID,
		sink:           opts.Sink,
		clock:          opts.Clock,
		timestampClock: opts.TimestampClock,
		state: engineState{
			pressure:   0,
			step:       0,
			lifecycle:  LifecycleInit,
			lastDelta:  0,
			lastStepAt: now,
		},
	}
	e.emit("engine.init", map[string]any{"pressure": 0.0})
	return e, nil
}

// Config returns the engine's configuration.
func (e *PressureEngine) Config() PressureConfig { return e.cfg }

// ExecutionID returns the execution this engine bounds.
func (e *PressureEngine) ExecutionID() string { return e.executionID }

// Pressure returns the current pressure.
func (e *PressureEngine) Pressure() float64 {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.state.pressure
}

// Lifecycle returns the current lifecycle state.
func (e *PressureEngine) Lifecycle() Lifecycle {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.state.lifecycle
}

// SpendUSD returns cumulative spend for this execution. Always 0 unless
// PressureConfig.ModelCosts is populated.
func (e *PressureEngine) SpendUSD() float64 {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.state.spendUSD
}

// Snapshot returns a consistent read of engine state.
func (e *PressureEngine) Snapshot() Snapshot {
	e.mu.Lock()
	defer e.mu.Unlock()
	return e.snapshotLocked()
}

func (e *PressureEngine) snapshotLocked() Snapshot {
	return Snapshot{
		Pressure:   e.state.pressure,
		Step:       e.state.step,
		Lifecycle:  e.state.lifecycle,
		LastDelta:  e.state.lastDelta,
		LastStepAt: e.state.lastStepAt,
		SpendUSD:   e.state.spendUSD,
	}
}

func clamp01(v float64) float64 {
	if v < 0 {
		return 0
	}
	if v > 1 {
		return 1
	}
	return v
}

// Step accounts for a unit of work and advances the engine.
//
// The order of operations is normative (spec/pressure/README.md; ported
// from crates/core/src/engine.rs). Deviation fails the conformance vectors:
//
//  1. LOCKED rejects the step, emits engine.step.rejected, mutates nothing.
//  2. elapsed = max(now - lastStepAt, 0)   — a backwards clock cannot buy decay.
//  3. delta  = tokens/1000*Kt + tools*Ku + depth*Kd
//  4. decay  = dissipationPerStep + elapsed*dissipationPerSecond
//  5. pressure = clamp(pressure + delta - decay, 0, 1)
//  6. emit engine.step with the POST-step pressure
//  7. release check FIRST (>= releaseThreshold), then escalation.
//
// ESCALATED still accepts further steps. Only LOCKED refuses.
func (e *PressureEngine) Step(work StepInput) StepOutcome {
	e.mu.Lock()
	if e.state.lifecycle == LifecycleLocked {
		e.mu.Unlock()
		e.emit("engine.step.rejected", map[string]any{
			"reason":           "locked",
			"requested_tokens": work.Tokens,
			"requested_tools":  work.ToolCalls,
		})
		return OutcomeLocked
	}

	now := e.clock()
	elapsed := now - e.state.lastStepAt
	if elapsed < 0 {
		elapsed = 0
	}

	delta := (float64(work.Tokens)/1000.0)*e.cfg.TokenCoefficient +
		float64(work.ToolCalls)*e.cfg.ToolCoefficient +
		float64(work.Depth)*e.cfg.DepthCoefficient
	decay := e.cfg.DissipationPerStep + elapsed*e.cfg.DissipationPerSecond

	e.state.pressure = clamp01(e.state.pressure + delta - decay)
	e.state.step++
	e.state.lastDelta = delta - decay
	e.state.lastStepAt = now
	e.state.lifecycle = LifecycleRunning

	stepSpend := e.stepSpendLocked(work)
	e.state.spendUSD += stepSpend

	data := map[string]any{
		"step":       e.state.step,
		"pressure":   e.state.pressure,
		"delta":      delta,
		"decay":      decay,
		"tokens":     work.Tokens,
		"tool_calls": work.ToolCalls,
		"depth":      work.Depth,
		"tag":        tagValue(work.Tag),
	}
	// spend_usd is an optional, additive field: it appears only when the
	// operator configured ModelCosts. Existing event consumers are unaffected.
	if len(e.cfg.ModelCosts) > 0 {
		data["spend_usd"] = e.state.spendUSD
	}

	pressureNow := e.state.pressure
	spendNow := e.state.spendUSD
	e.mu.Unlock() // release before emitting — never emit under lock

	e.emit("engine.step", data)

	// Hard USD ceiling, independent of pressure. Reuses the lock path so
	// the Lifecycle wire format stays frozen.
	if e.cfg.BudgetUSD > 0 && spendNow >= e.cfg.BudgetUSD {
		e.mu.Lock()
		e.state.pressure = 0
		e.state.lifecycle = LifecycleLocked
		e.mu.Unlock()
		e.emit("engine.locked", map[string]any{
			"reason":     "budget_exceeded",
			"spend_usd":  spendNow,
			"budget_usd": e.cfg.BudgetUSD,
		})
		return OutcomeLocked
	}

	switch {
	case pressureNow >= e.cfg.ReleaseThreshold:
		e.emit("engine.release", map[string]any{
			"pressure":  pressureNow,
			"threshold": e.cfg.ReleaseThreshold,
		})
		e.mu.Lock()
		e.state.pressure = 0
		if e.cfg.PostReleaseLock {
			e.state.lifecycle = LifecycleLocked
			e.mu.Unlock()
			e.emit("engine.locked", map[string]any{"reason": "post_release_lock"})
		} else {
			e.state.lifecycle = LifecycleRunning
			e.mu.Unlock()
		}
		return OutcomeReleased

	case pressureNow >= e.cfg.EscalationThreshold:
		e.mu.Lock()
		e.state.lifecycle = LifecycleEscalated
		e.mu.Unlock()
		e.emit("engine.escalation", map[string]any{
			"pressure":  pressureNow,
			"threshold": e.cfg.EscalationThreshold,
		})
		return OutcomeEscalated

	default:
		return OutcomeOK
	}
}

// stepSpendLocked computes USD spend for this step. Caller holds e.mu.
func (e *PressureEngine) stepSpendLocked(work StepInput) float64 {
	if len(e.cfg.ModelCosts) == 0 {
		return 0
	}
	perMillion, ok := e.cfg.ModelCosts[work.Model]
	if !ok {
		return 0
	}
	return float64(work.Tokens) / 1_000_000.0 * perMillion
}

// Reset clears pressure and the step counter, returns the lifecycle to
// INIT, and emits engine.reset. This is the only way out of LOCKED.
func (e *PressureEngine) Reset() Snapshot {
	now := e.clock()
	e.mu.Lock()
	e.state.pressure = 0
	e.state.step = 0
	e.state.lastDelta = 0
	e.state.lastStepAt = now
	e.state.lifecycle = LifecycleInit
	e.state.spendUSD = 0
	e.mu.Unlock()

	e.emit("engine.reset", map[string]any{"pressure": 0.0})
	return e.Snapshot()
}

func (e *PressureEngine) emit(kind string, data map[string]any) {
	e.sink.Emit(audit.NewEvent(e.executionID, kind, e.timestampClock(), data))
}

func tagValue(tag *string) any {
	if tag == nil {
		return nil
	}
	return *tag
}
