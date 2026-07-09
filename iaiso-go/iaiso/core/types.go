// Package core holds the IAIso runtime: the pressure engine and the
// BoundedExecution facade built on top of it.
//
// # Trust boundary
//
// This package runs INSIDE the agent process. It bounds a COOPERATING
// agent — one that calls into the engine and honours ErrLocked. It does
// not contain an agent that executes arbitrary code in its own process:
// such an agent can monkeypatch, recover from, or simply never call these
// checks. For adversarial containment, bind these thresholds to an
// out-of-process anchor. See LIMITATIONS.md.
package core

import "time"

// Lifecycle is the engine's high-level state.
//
// Wire-format strings — these MUST match the Python, Node, Rust, Java, PHP
// and C# SDKs exactly. Six ports depend on them; they are frozen.
type Lifecycle string

const (
	LifecycleInit      Lifecycle = "init"
	LifecycleRunning   Lifecycle = "running"
	LifecycleEscalated Lifecycle = "escalated"
	LifecycleReleased  Lifecycle = "released"
	LifecycleLocked    Lifecycle = "locked"
)

// String returns the wire-format representation.
func (l Lifecycle) String() string { return string(l) }

// StepOutcome is the result of a single Step call. Wire-format strings;
// frozen for the same reason as Lifecycle.
//
// ESCALATED does not stop execution — it is a signal. Only LOCKED refuses
// further steps. This is deliberate. An escalation delivered to a log
// nobody reads is not human-in-the-loop.
type StepOutcome string

const (
	OutcomeOK        StepOutcome = "ok"
	OutcomeEscalated StepOutcome = "escalated"
	OutcomeReleased  StepOutcome = "released"
	OutcomeLocked    StepOutcome = "locked"
)

// String returns the wire-format representation.
func (o StepOutcome) String() string { return string(o) }

// Aliases kept because the published README and downstream code use the
// StepOutcome* spelling.
const (
	StepOutcomeOK        = OutcomeOK
	StepOutcomeEscalated = OutcomeEscalated
	StepOutcomeReleased  = OutcomeReleased
	StepOutcomeLocked    = OutcomeLocked
)

// Clock returns fractional seconds. The conformance vectors drive the
// engine with a scripted clock, so clock injection is mandatory rather
// than a testing convenience.
type Clock func() float64

// Wallclock is the default Clock: Unix time with sub-second resolution.
func Wallclock() Clock {
	return func() float64 { return float64(time.Now().UnixNano()) / 1e9 }
}

// ScriptedClock returns a Clock that yields seq in order, repeating the
// final element once exhausted. Used by the conformance runner.
func ScriptedClock(seq []float64) Clock {
	i := 0
	return func() float64 {
		if len(seq) == 0 {
			return 0
		}
		if i < len(seq) {
			v := seq[i]
			i++
			return v
		}
		return seq[len(seq)-1]
	}
}
