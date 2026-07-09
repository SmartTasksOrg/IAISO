package core

import (
	"crypto/rand"
	"encoding/hex"
	"errors"
	"fmt"
	"sync"

	"github.com/iaiso/iaiso-go/iaiso/audit"
)

// ErrLocked is returned once the execution has locked. Only Reset clears it.
//
// Swallowing this error defeats the framework. It is the single most
// important error in the SDK.
var ErrLocked = errors.New("iaiso: execution is locked; call Reset() before continuing")

// BoundedExecutionOptions configures a BoundedExecution.
type BoundedExecutionOptions struct {
	// ExecutionID; a random one is generated when empty.
	ExecutionID string
	// Config defaults to DefaultConfig().
	Config *PressureConfig
	// AuditSink defaults to audit.NullSink (which strict mode rejects).
	AuditSink audit.Sink
	// Clock and TimestampClock default to Wallclock.
	Clock          Clock
	TimestampClock Clock
	// EnforcementMode: "permissive" (default) or "strict".
	EnforcementMode string
	// CalibrationArtifact satisfies the strict-mode calibration condition.
	CalibrationArtifact string
}

// BoundedExecution wraps a PressureEngine with execution-level audit
// emission and ergonomic accounting helpers.
type BoundedExecution struct {
	engine         *PressureEngine
	sink           audit.Sink
	timestampClock Clock

	mu     sync.Mutex
	closed bool
}

// Start constructs a BoundedExecution. The caller is responsible for
// calling Close; prefer Run, which guarantees it.
func Start(opts BoundedExecutionOptions) (*BoundedExecution, error) {
	execID := opts.ExecutionID
	if execID == "" {
		execID = "exec-" + randomID()
	}
	cfg := DefaultConfig()
	if opts.Config != nil {
		cfg = *opts.Config
	}
	sink := opts.AuditSink
	if sink == nil {
		sink = audit.NewNullSink()
	}
	clk := opts.Clock
	if clk == nil {
		clk = Wallclock()
	}
	tsClk := opts.TimestampClock
	if tsClk == nil {
		tsClk = Wallclock()
	}

	engine, err := NewPressureEngine(cfg, EngineOptions{
		ExecutionID:         execID,
		Sink:                sink,
		Clock:               clk,
		TimestampClock:      tsClk,
		EnforcementMode:     opts.EnforcementMode,
		CalibrationArtifact: opts.CalibrationArtifact,
	})
	if err != nil {
		return nil, err
	}
	return &BoundedExecution{engine: engine, sink: sink, timestampClock: tsClk}, nil
}

// Run executes fn inside a BoundedExecution and guarantees Close is called,
// even if fn returns an error or panics.
func Run(opts BoundedExecutionOptions, fn func(*BoundedExecution) error) error {
	exec, err := Start(opts)
	if err != nil {
		return err
	}
	errored := true
	defer func() { exec.Close(errored) }()
	if err := fn(exec); err != nil {
		return err
	}
	errored = false
	return nil
}

// Engine exposes the underlying engine.
func (x *BoundedExecution) Engine() *PressureEngine { return x.engine }

// ExecutionID returns the execution identifier.
func (x *BoundedExecution) ExecutionID() string { return x.engine.ExecutionID() }

// Snapshot returns engine state.
func (x *BoundedExecution) Snapshot() Snapshot { return x.engine.Snapshot() }

// RecordTokens accounts for tokens with an optional tag.
func (x *BoundedExecution) RecordTokens(tokens uint64, tag string) (StepOutcome, error) {
	return x.account(StepInput{Tokens: tokens, Tag: optional(tag)})
}

// RecordToolCall accounts for one tool invocation and its tokens. Tool
// calls are usually the expensive operations — retrieval, code execution —
// which is why ToolCoefficient prices them separately from tokens.
func (x *BoundedExecution) RecordToolCall(name string, tokens uint64) (StepOutcome, error) {
	return x.account(StepInput{Tokens: tokens, ToolCalls: 1, Tag: optional(name)})
}

// RecordStep is the general accounting entry point.
func (x *BoundedExecution) RecordStep(work StepInput) (StepOutcome, error) {
	return x.account(work)
}

func (x *BoundedExecution) account(work StepInput) (StepOutcome, error) {
	outcome := x.engine.Step(work)
	if outcome == OutcomeLocked {
		return outcome, ErrLocked
	}
	return outcome, nil
}

// Check reports the current posture without advancing the engine. Call it
// BEFORE issuing an expensive provider request: the request is then never
// sent when the execution is already locked.
func (x *BoundedExecution) Check() StepOutcome {
	switch x.engine.Lifecycle() {
	case LifecycleLocked:
		return OutcomeLocked
	case LifecycleEscalated:
		return OutcomeEscalated
	default:
		return OutcomeOK
	}
}

// Reset clears pressure and unlocks the execution.
func (x *BoundedExecution) Reset() Snapshot { return x.engine.Reset() }

// SpendUSD returns cumulative spend. Zero unless ModelCosts is configured.
func (x *BoundedExecution) SpendUSD() float64 { return x.engine.SpendUSD() }

// Close emits execution.closed exactly once.
func (x *BoundedExecution) Close(errored bool) {
	x.mu.Lock()
	if x.closed {
		x.mu.Unlock()
		return
	}
	x.closed = true
	x.mu.Unlock()

	snap := x.engine.Snapshot()
	data := map[string]any{
		"final_pressure":  snap.Pressure,
		"final_lifecycle": snap.Lifecycle.String(),
		"exception":       exceptionValue(errored),
	}
	if x.engine.Config().ModelCosts != nil {
		data["spend_usd"] = snap.SpendUSD
	}
	x.sink.Emit(audit.NewEvent(x.engine.ExecutionID(), "execution.closed", x.timestampClock(), data))
}

func exceptionValue(errored bool) any {
	if errored {
		return "error"
	}
	return nil
}

func optional(s string) *string {
	if s == "" {
		return nil
	}
	return &s
}

func randomID() string {
	b := make([]byte, 8)
	if _, err := rand.Read(b); err != nil {
		return fmt.Sprintf("%016x", 0)
	}
	return hex.EncodeToString(b)
}
