package coordination

import (
	"testing"

	"github.com/iaiso/iaiso-go/iaiso/audit"
	"github.com/iaiso/iaiso-go/iaiso/policy"
)

func newCoord(t *testing.T, esc, rel float64, cb Callbacks) *SharedPressureCoordinator {
	t.Helper()
	c, err := NewSharedPressureCoordinator(CoordinatorOptions{
		CoordinatorID: "test", EscalationThreshold: esc, ReleaseThreshold: rel,
		Aggregator: policy.SumAggregator{}, Callbacks: cb, Sink: audit.NewMemorySink(),
	})
	if err != nil {
		t.Fatal(err)
	}
	return c
}

func TestFleetSumCrossesWhereNoSingleWorkerDoes(t *testing.T) {
	// The reason the coordinator exists: three workers at 0.4 are each well
	// under any per-agent cap, and together they are over the fleet limit.
	var escalations int
	c := newCoord(t, 1.0, 2.0, Callbacks{OnEscalation: func(Snapshot) { escalations++ }})
	c.Update("w1", 0.4)
	c.Update("w2", 0.4)
	snap := c.Update("w3", 0.4)
	if !snap.Escalated {
		t.Fatalf("aggregate %v did not escalate at 1.0", snap.Aggregate)
	}
	if escalations != 1 {
		t.Fatalf("escalation callback fired %d times, want 1", escalations)
	}
}

func TestEscalationDoesNotRefireWhileEscalated(t *testing.T) {
	var n int
	c := newCoord(t, 1.0, 5.0, Callbacks{OnEscalation: func(Snapshot) { n++ }})
	c.Update("w1", 0.6)
	c.Update("w2", 0.6) // crosses
	c.Update("w2", 0.7) // still over; must not refire
	if n != 1 {
		t.Fatalf("escalation fired %d times, want 1", n)
	}
}

func TestReleaseZeroesEveryWorker(t *testing.T) {
	var released bool
	c := newCoord(t, 1.0, 1.5, Callbacks{OnRelease: func(Snapshot) { released = true }})
	c.Update("w1", 0.8)
	snap := c.Update("w2", 0.8)
	if !snap.Released || !released {
		t.Fatalf("aggregate %v did not release at 1.5", snap.Aggregate)
	}
	after := c.Snapshot()
	if after.Aggregate != 0 {
		t.Fatalf("post-release aggregate = %v, want 0", after.Aggregate)
	}
	if len(after.Pressures) != 2 {
		t.Fatal("release deregistered workers; it must only zero them")
	}
}

func TestReleaseMustExceedEscalation(t *testing.T) {
	_, err := NewSharedPressureCoordinator(CoordinatorOptions{
		EscalationThreshold: 2.0, ReleaseThreshold: 1.0,
	})
	if err == nil {
		t.Fatal("accepted release_threshold below escalation_threshold")
	}
}

func TestUnregisterRemovesPressure(t *testing.T) {
	c := newCoord(t, 10, 20, Callbacks{})
	c.Update("w1", 0.5)
	c.Update("w2", 0.5)
	c.Unregister("w1")
	if got := c.Snapshot().Aggregate; got != 0.5 {
		t.Fatalf("aggregate = %v, want 0.5", got)
	}
}

func TestScriptSHAIsStable(t *testing.T) {
	// Every port must EVAL the same source, so the SHA must not drift.
	// If this fails, the Lua script was edited and cross-language EVALSHA
	// caches have diverged.
	if got := ScriptSHA(); len(got) != 40 {
		t.Fatalf("SHA %q is not a 40-char hex digest", got)
	}
	if a, b := ScriptSHA(), ScriptSHA(); a != b {
		t.Fatal("ScriptSHA is not deterministic")
	}
}

func TestPressuresKeyFormat(t *testing.T) {
	c := &RedisCoordinator{id: "prod", prefix: DefaultKeyPrefix}
	if got := c.PressuresKey(); got != "iaiso:coord:prod:pressures" {
		t.Fatalf("key = %q", got)
	}
}

func TestParseHGetAll(t *testing.T) {
	got, err := parseHGetAll([]any{"w1", "0.25", "w2", "0.5"})
	if err != nil {
		t.Fatal(err)
	}
	if got["w1"] != 0.25 || got["w2"] != 0.5 {
		t.Fatalf("parsed %v", got)
	}
	if _, err := parseHGetAll([]any{"w1"}); err == nil {
		t.Fatal("accepted an odd-length HGETALL array")
	}
}
