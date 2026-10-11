package audit

import (
	"os"
	"sync"
)

// JSONLFileSink appends one JSON event per line to a file, opening the file
// under a mutex on each Emit so multiple engines can share one sink.
//
// For regulated workloads this is the sink to use: unlike WebhookSink it
// does not drop under backpressure. Ship the file with a log forwarder.
type JSONLFileSink struct {
	mu   sync.Mutex
	path string
	errs int
}

// NewJSONLFileSink appends events to path, creating it if absent.
func NewJSONLFileSink(path string) *JSONLFileSink { return &JSONLFileSink{path: path} }

// Path returns the destination file.
func (s *JSONLFileSink) Path() string { return s.path }

// Errors reports how many events failed to serialise or write.
func (s *JSONLFileSink) Errors() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.errs
}

// Emit implements Sink.
func (s *JSONLFileSink) Emit(ev Event) {
	b, err := ev.JSON()
	s.mu.Lock()
	defer s.mu.Unlock()
	if err != nil {
		s.errs++
		return
	}
	f, err := os.OpenFile(s.path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		s.errs++
		return
	}
	defer func() { _ = f.Close() }()
	if _, err := f.Write(append(b, '\n')); err != nil {
		s.errs++
	}
}
