package core

import (
	"bytes"
	"encoding/json"
	"fmt"
)

// DecodeStepInput parses untrusted JSON (snake_case keys, as in the spec
// vectors and audit events) into a StepInput. Counts are uint64, so negative,
// fractional, boolean and string values are refused by the decoder; JSON null
// and unknown keys are refused here, because encoding/json would otherwise
// turn null into 0 and ignore typos such as "token".
func DecodeStepInput(raw []byte) (StepInput, error) {
	var probe map[string]json.RawMessage
	if err := json.Unmarshal(raw, &probe); err != nil {
		return StepInput{}, fmt.Errorf("step input: %w", err)
	}
	for k, v := range probe {
		switch k {
		case "tokens", "tool_calls", "depth":
			if bytes.Equal(bytes.TrimSpace(v), []byte("null")) {
				return StepInput{}, fmt.Errorf("step input: %s must be a non-negative integer, got null", k)
			}
		}
	}
	var w struct {
		Tokens    uint64  `json:"tokens"`
		ToolCalls uint64  `json:"tool_calls"`
		Depth     uint64  `json:"depth"`
		Tag       *string `json:"tag"`
		Model     string  `json:"model"`
	}
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&w); err != nil {
		return StepInput{}, fmt.Errorf("step input: %w", err)
	}
	return StepInput{Tokens: w.Tokens, ToolCalls: w.ToolCalls, Depth: w.Depth, Tag: w.Tag, Model: w.Model}, nil
}
