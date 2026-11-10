package audit

import (
	"bufio"
	"io"
	"os"
	"sync"
)

// StdoutSink writes one JSON event per line to an io.Writer (os.Stdout by
// default). Write errors are dropped: audit delivery is best-effort and a
// failing sink must never fail the agent's step.
type StdoutSink struct {
	mu sync.Mutex
	w  io.Writer
}

// NewStdoutSink writes to os.Stdout.
func NewStdoutSink() *StdoutSink { return &StdoutSink{w: os.Stdout} }

// NewWriterSink writes to an arbitrary writer.
func NewWriterSink(w io.Writer) *StdoutSink { return &StdoutSink{w: w} }

// Emit implements Sink.
func (s *StdoutSink) Emit(ev Event) {
	b, err := ev.JSON()
	if err != nil {
		return
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	bw := bufio.NewWriter(s.w)
	_, _ = bw.Write(b)
	_, _ = bw.WriteString("\n")
	_ = bw.Flush()
}
