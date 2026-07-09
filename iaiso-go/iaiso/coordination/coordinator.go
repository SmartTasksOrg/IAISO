// Package coordination aggregates pressure across a fleet of executions.
//
// A per-agent cap does not bound a fleet: a hundred agents can each spend
// just under it. The coordinator sums (or means, or maxes) pressure across
// workers so the fleet has a ceiling too.
//
// The in-memory coordinator is single-process. Only the Redis coordinator
// is normative for cross-language interop, because its wire format — the
// keyspace and Lua script in spec/coordinator/README.md §1 — is the
// contract that a Go worker and a Python worker share.
package coordination

import (
	"fmt"
	"sort"
	"sync"

	"github.com/iaiso/iaiso-go/iaiso/audit"
	"github.com/iaiso/iaiso-go/iaiso/policy"
)

// Snapshot is the coordinator's view of the fleet at one instant.
type Snapshot struct {
	CoordinatorID string
	Aggregate     float64
	Pressures     map[string]float64
	Escalated     bool
	Released      bool
}

// Callbacks fire on the process that observed a threshold transition.
//
// They are NOT exactly-once across the fleet. If every worker must react,
// subscribe to the event stream; do not rely on per-process callbacks for
// fan-out. See spec/coordinator/README.md §6.
type Callbacks struct {
	OnEscalation func(Snapshot)
	OnRelease    func(Snapshot)
}

// CoordinatorOptions configures a SharedPressureCoordinator.
type CoordinatorOptions struct {
	CoordinatorID       string
	EscalationThreshold float64
	ReleaseThreshold    float64
	Aggregator          policy.Aggregator
	Callbacks           Callbacks
	Sink                audit.Sink
	// Clock stamps emitted events. Defaults to a wallclock.
	Clock func() float64
}

// SharedPressureCoordinator tracks pressures for a single-process fleet.
type SharedPressureCoordinator struct {
	id         string
	escalation float64
	release    float64
	agg        policy.Aggregator
	cb         Callbacks
	sink       audit.Sink
	clock      func() float64

	mu        sync.Mutex
	pressures map[string]float64
	escalated bool
}

// NewSharedPressureCoordinator validates thresholds and returns a
// coordinator. Like the engine, release must exceed escalation.
func NewSharedPressureCoordinator(opts CoordinatorOptions) (*SharedPressureCoordinator, error) {
	if opts.CoordinatorID == "" {
		opts.CoordinatorID = "default"
	}
	if opts.EscalationThreshold == 0 && opts.ReleaseThreshold == 0 {
		d := policy.DefaultCoordinatorConfig()
		opts.EscalationThreshold = d.EscalationThreshold
		opts.ReleaseThreshold = d.ReleaseThreshold
	}
	if opts.EscalationThreshold < 0 || opts.ReleaseThreshold < 0 {
		return nil, fmt.Errorf("coordination: thresholds must be non-negative")
	}
	if opts.ReleaseThreshold <= opts.EscalationThreshold {
		return nil, fmt.Errorf(
			"coordination: release_threshold must exceed escalation_threshold (%v <= %v)",
			opts.ReleaseThreshold, opts.EscalationThreshold)
	}
	if opts.Aggregator == nil {
		opts.Aggregator = policy.SumAggregator{}
	}
	if opts.Sink == nil {
		opts.Sink = audit.NewNullSink()
	}
	if opts.Clock == nil {
		opts.Clock = defaultClock
	}
	return &SharedPressureCoordinator{
		id:         opts.CoordinatorID,
		escalation: opts.EscalationThreshold,
		release:    opts.ReleaseThreshold,
		agg:        opts.Aggregator,
		cb:         opts.Callbacks,
		sink:       opts.Sink,
		clock:      opts.Clock,
		pressures:  map[string]float64{},
	}, nil
}

// Register adds an execution at zero pressure.
func (c *SharedPressureCoordinator) Register(executionID string) {
	c.mu.Lock()
	if _, ok := c.pressures[executionID]; !ok {
		c.pressures[executionID] = 0
	}
	c.mu.Unlock()
	c.emit("coordinator.registered", map[string]any{"execution_id": executionID})
}

// Unregister removes an execution from the fleet.
func (c *SharedPressureCoordinator) Unregister(executionID string) {
	c.mu.Lock()
	delete(c.pressures, executionID)
	c.mu.Unlock()
	c.emit("coordinator.unregistered", map[string]any{"execution_id": executionID})
}

// Update records a worker's pressure and returns the post-write fleet view.
func (c *SharedPressureCoordinator) Update(executionID string, pressure float64) Snapshot {
	c.mu.Lock()
	c.pressures[executionID] = pressure
	snap := c.snapshotLocked()
	wasEscalated := c.escalated

	switch {
	case snap.Aggregate >= c.release:
		snap.Escalated, snap.Released = true, true
		for k := range c.pressures {
			c.pressures[k] = 0
		}
		c.escalated = false
	case snap.Aggregate >= c.escalation:
		snap.Escalated = true
		c.escalated = true
	default:
		c.escalated = false
	}
	c.mu.Unlock()

	if snap.Released {
		c.emit("coordinator.release", map[string]any{
			"aggregate": snap.Aggregate, "threshold": c.release,
		})
		if c.cb.OnRelease != nil {
			c.cb.OnRelease(snap)
		}
	} else if snap.Escalated && !wasEscalated {
		c.emit("coordinator.escalation", map[string]any{
			"aggregate": snap.Aggregate, "threshold": c.escalation,
		})
		if c.cb.OnEscalation != nil {
			c.cb.OnEscalation(snap)
		}
	}
	return snap
}

// Snapshot returns the current fleet view.
func (c *SharedPressureCoordinator) Snapshot() Snapshot {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.snapshotLocked()
}

func (c *SharedPressureCoordinator) snapshotLocked() Snapshot {
	pressures := make(map[string]float64, len(c.pressures))
	for k, v := range c.pressures {
		pressures[k] = v
	}
	return Snapshot{
		CoordinatorID: c.id,
		Aggregate:     c.agg.Aggregate(pressures),
		Pressures:     pressures,
	}
}

// Reset zeroes every registered execution without deregistering any.
func (c *SharedPressureCoordinator) Reset() Snapshot {
	c.mu.Lock()
	for k := range c.pressures {
		c.pressures[k] = 0
	}
	c.escalated = false
	snap := c.snapshotLocked()
	c.mu.Unlock()
	c.emit("coordinator.reset", map[string]any{"aggregate": 0.0})
	return snap
}

// ExecutionIDs returns the registered executions, sorted.
func (c *SharedPressureCoordinator) ExecutionIDs() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := make([]string, 0, len(c.pressures))
	for k := range c.pressures {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func (c *SharedPressureCoordinator) emit(kind string, data map[string]any) {
	c.sink.Emit(audit.NewEvent("coord:"+c.id, kind, c.clock(), data))
}
