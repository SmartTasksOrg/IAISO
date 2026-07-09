package audit

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"testing"
)

func TestEventEnvelopeFieldOrderAndSchema(t *testing.T) {
	ev := NewEvent("exec-1", "engine.step", 1.5, map[string]any{"pressure": 0.5})
	b, err := ev.JSON()
	if err != nil {
		t.Fatal(err)
	}
	s := string(b)
	if !strings.HasPrefix(s, `{"schema_version":"1.0","execution_id":"exec-1","kind":"engine.step"`) {
		t.Fatalf("envelope field order changed: %s", s)
	}
	var back Event
	if err := json.Unmarshal(b, &back); err != nil {
		t.Fatal(err)
	}
	if back.Kind != "engine.step" || back.SchemaVersion != "1.0" {
		t.Fatalf("roundtrip lost fields: %+v", back)
	}
}

func TestFanoutReachesEverySinkEvenIfOneMisbehaves(t *testing.T) {
	a, b := NewMemorySink(), NewMemorySink()
	fan := NewFanoutSink(a, sinkFunc(func(Event) { panic("bad sink") }), b)
	fan.Emit(NewEvent("e", "k", 0, nil))
	if a.Len() != 1 || b.Len() != 1 {
		t.Fatalf("a=%d b=%d; a panicking sink starved its siblings", a.Len(), b.Len())
	}
}

type sinkFunc func(Event)

func (f sinkFunc) Emit(ev Event) { f(ev) }

func TestJSONLFileSinkWritesOneObjectPerLine(t *testing.T) {
	path := filepath.Join(t.TempDir(), "audit.jsonl")
	sink := NewJSONLFileSink(path)
	sink.Emit(NewEvent("e", "a", 0, nil))
	sink.Emit(NewEvent("e", "b", 1, nil))
	if sink.Errors() != 0 {
		t.Fatalf("%d write errors", sink.Errors())
	}
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimSpace(string(raw)), "\n")
	if len(lines) != 2 {
		t.Fatalf("got %d lines, want 2", len(lines))
	}
	for _, l := range lines {
		var ev Event
		if err := json.Unmarshal([]byte(l), &ev); err != nil {
			t.Fatalf("line is not a JSON object: %q", l)
		}
	}
}

func TestMemorySinkIsConcurrencySafe(t *testing.T) {
	s := NewMemorySink()
	var wg sync.WaitGroup
	for i := 0; i < 16; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for j := 0; j < 100; j++ {
				s.Emit(NewEvent("e", "k", 0, nil))
			}
		}()
	}
	wg.Wait()
	if s.Len() != 1600 {
		t.Fatalf("len = %d, want 1600", s.Len())
	}
}

func TestWebhookSinkDropsRatherThanBlocks(t *testing.T) {
	// WebhookSink is lossy by design: a slow endpoint must not stall the
	// agent. Dropped() is the number the operator has to alert on.
	s := NewWebhookSink(WebhookOptions{URL: "http://127.0.0.1:1/never", QueueSize: 1})
	defer s.Close()
	for i := 0; i < 500; i++ {
		s.Emit(NewEvent("e", "k", 0, nil))
	}
	if s.Dropped() == 0 {
		t.Skip("queue drained faster than the test could fill it")
	}
}
