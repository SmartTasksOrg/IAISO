// Package audit defines the IAIso audit event envelope and the pluggable
// sinks that carry events out of the agent process.
//
// The envelope is normatively specified in spec/events/README.md §1 and is
// stable within a MAJOR spec version. Field order in the marshalled JSON is
// schema_version, execution_id, kind, timestamp, data — matching the Python,
// Node and Rust reference SDKs byte-for-byte.
package audit

import "encoding/json"

// SchemaVersion is the version string stamped into every event envelope.
const SchemaVersion = "1.0"

// Event is a canonical IAIso audit event.
//
// Struct field order is load-bearing: encoding/json emits object keys in
// declaration order, and the reference SDKs agree on that order.
type Event struct {
	SchemaVersion string         `json:"schema_version"`
	ExecutionID   string         `json:"execution_id"`
	Kind          string         `json:"kind"`
	Timestamp     float64        `json:"timestamp"`
	Data          map[string]any `json:"data"`
}

// NewEvent constructs an Event stamped with the current SchemaVersion.
// A nil data map is normalised to an empty object so the envelope always
// satisfies spec/events/envelope.schema.json (`data` is required).
func NewEvent(executionID, kind string, timestamp float64, data map[string]any) Event {
	if data == nil {
		data = map[string]any{}
	}
	return Event{
		SchemaVersion: SchemaVersion,
		ExecutionID:   executionID,
		Kind:          kind,
		Timestamp:     timestamp,
		Data:          data,
	}
}

// JSON renders the event as a single-line JSON object. Map keys inside
// `data` are emitted in sorted order by encoding/json, which makes the
// output deterministic across runs and across ports.
func (e Event) JSON() ([]byte, error) { return json.Marshal(e) }

// Clone returns a deep-enough copy for fan-out to sinks that mutate.
func (e Event) Clone() Event {
	d := make(map[string]any, len(e.Data))
	for k, v := range e.Data {
		d[k] = v
	}
	e.Data = d
	return e
}
