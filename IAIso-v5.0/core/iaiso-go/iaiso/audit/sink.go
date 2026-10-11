package audit

import "sync"

// Sink receives audit events. Implementations SHOULD keep Emit off the
// agent's hot path and MUST NOT panic: sustained backpressure is signalled
// by dropping events (and incrementing a drop counter), never by failing
// the caller's step.
//
// Emit must be safe for concurrent use. The engine never holds its state
// lock while calling Emit, so a sink may safely call back into the engine.
type Sink interface {
	Emit(ev Event)
}

// NullSink discards every event.
//
// A NullSink as the only audit sink means escalations are unobservable.
// enforcement_mode: strict refuses to boot in that configuration — see
// core.BootGuard and LIMITATIONS.md.
type NullSink struct{}

// NewNullSink returns a sink that discards every event.
func NewNullSink() *NullSink { return &NullSink{} }

// Emit implements Sink.
func (*NullSink) Emit(Event) {}

// MemorySink retains every event in order. Intended for tests and for the
// conformance runner, which asserts on the exact emitted sequence.
type MemorySink struct {
	mu     sync.Mutex
	events []Event
}

// NewMemorySink returns an empty in-memory sink.
func NewMemorySink() *MemorySink { return &MemorySink{} }

// Emit implements Sink.
func (s *MemorySink) Emit(ev Event) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.events = append(s.events, ev)
}

// Events returns a snapshot copy of the retained events.
func (s *MemorySink) Events() []Event {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]Event, len(s.events))
	copy(out, s.events)
	return out
}

// Len reports how many events have been emitted.
func (s *MemorySink) Len() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.events)
}

// Clear drops all retained events.
func (s *MemorySink) Clear() {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.events = nil
}
