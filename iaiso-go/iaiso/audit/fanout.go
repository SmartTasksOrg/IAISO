package audit

// FanoutSink broadcasts every event to each child sink, in order. A panic
// or slow write in one child does not prevent delivery to the others.
type FanoutSink struct {
	sinks []Sink
}

// NewFanoutSink builds a broadcasting sink over the supplied children.
func NewFanoutSink(sinks ...Sink) *FanoutSink { return &FanoutSink{sinks: sinks} }

// Emit implements Sink.
func (s *FanoutSink) Emit(ev Event) {
	for _, child := range s.sinks {
		func(c Sink) {
			defer func() { _ = recover() }()
			c.Emit(ev.Clone())
		}(child)
	}
}

// Sinks returns the child sinks.
func (s *FanoutSink) Sinks() []Sink { return s.sinks }
