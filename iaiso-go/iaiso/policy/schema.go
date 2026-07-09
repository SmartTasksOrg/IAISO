// Package policy loads and validates IAIso policy files (JSON or YAML)
// against spec/policy/policy.schema.json.
//
// Policy is TRUSTED INPUT. A malicious operator who sets token_coefficient
// to 0 and post_release_lock to false has disabled the framework, and IAIso
// will not stop them. Sign your policy files and review them like code.
// See LIMITATIONS.md.
package policy

import (
	"encoding/json"
	"errors"
	"fmt"

	"github.com/iaiso/iaiso-go/iaiso/consent"
)

// ErrPolicy is wrapped by every policy error.
var ErrPolicy = errors.New("policy error")

// ValidationError names the offending JSON path. The message always begins
// with that path, which is what spec/policy/vectors.json asserts on.
type ValidationError struct {
	Path    string
	Message string
}

func (e *ValidationError) Error() string { return e.Message }
func (e *ValidationError) Unwrap() error { return ErrPolicy }

func verr(path, format string, args ...any) *ValidationError {
	return &ValidationError{Path: path, Message: fmt.Sprintf("%s: %s", path, fmt.Sprintf(format, args...))}
}

// SchemaVersion is the only accepted value of the top-level `version` key.
const SchemaVersion = "1"

var knownAggregators = map[string]bool{
	"sum": true, "mean": true, "max": true, "weighted_sum": true,
}

var knownEnforcementModes = map[string]bool{
	"permissive": true, "strict": true,
}

// asFloat accepts JSON numbers and YAML ints/floats. It deliberately does
// NOT accept numeric strings: `token_coefficient: "0.015"` is a type error,
// and silently coercing it would hide a typo in a safety-critical file.
func asFloat(v any) (float64, bool) {
	switch n := v.(type) {
	case float64:
		return n, true
	case float32:
		return float64(n), true
	case int:
		return float64(n), true
	case int64:
		return float64(n), true
	case uint64:
		return float64(n), true
	case json.Number:
		f, err := n.Float64()
		return f, err == nil
	}
	return 0, false
}

func asMap(v any) (map[string]any, bool) {
	m, ok := v.(map[string]any)
	return m, ok
}

// Validate checks doc against the normative rules in spec/policy/README.md,
// returning on the first violation.
func Validate(doc any) error {
	root, ok := asMap(doc)
	if !ok {
		return verr("$", "policy document must be a mapping")
	}

	rawVersion, present := root["version"]
	if !present {
		return verr("$", "required property 'version' missing")
	}
	version, ok := rawVersion.(string)
	if !ok || version != SchemaVersion {
		return verr("$.version", "must be exactly %q, got %v", SchemaVersion, rawVersion)
	}

	if err := validateEnforcementMode(root); err != nil {
		return err
	}
	if err := validatePressure(root); err != nil {
		return err
	}
	if err := validateCoordinator(root); err != nil {
		return err
	}
	if err := validateConsent(root); err != nil {
		return err
	}
	if md, present := root["metadata"]; present {
		if _, ok := asMap(md); !ok {
			return verr("$.metadata", "must be a mapping")
		}
	}
	return nil
}

func validateEnforcementMode(root map[string]any) error {
	raw, present := root["enforcement_mode"]
	if !present {
		return nil
	}
	s, ok := raw.(string)
	if !ok || !knownEnforcementModes[s] {
		return verr("$.enforcement_mode",
			"must be one of permissive|strict (got %v)", raw)
	}
	return nil
}

func validatePressure(root map[string]any) error {
	raw, present := root["pressure"]
	if !present {
		return nil
	}
	p, ok := asMap(raw)
	if !ok {
		return verr("$.pressure", "must be a mapping")
	}

	for _, f := range []string{
		"token_coefficient", "tool_coefficient", "depth_coefficient",
		"dissipation_per_step", "dissipation_per_second",
	} {
		v, present := p[f]
		if !present {
			continue
		}
		n, ok := asFloat(v)
		if !ok {
			return verr("$.pressure."+f, "expected number, got %T", v)
		}
		if n < 0 {
			return verr("$.pressure."+f, "must be non-negative (got %v)", n)
		}
	}

	for _, f := range []string{"escalation_threshold", "release_threshold"} {
		v, present := p[f]
		if !present {
			continue
		}
		n, ok := asFloat(v)
		if !ok {
			return verr("$.pressure."+f, "expected number, got %T", v)
		}
		if n < 0 || n > 1 {
			return verr("$.pressure."+f, "must be in [0, 1] (got %v)", n)
		}
	}

	if v, present := p["post_release_lock"]; present {
		if _, ok := v.(bool); !ok {
			return verr("$.pressure.post_release_lock", "expected boolean, got %T", v)
		}
	}

	esc, hasEsc := asFloat(p["escalation_threshold"])
	rel, hasRel := asFloat(p["release_threshold"])
	if hasEsc && hasRel && rel <= esc {
		return verr("$.pressure.release_threshold",
			"must exceed escalation_threshold (%v <= %v)", rel, esc)
	}

	if v, present := p["model_costs"]; present {
		costs, ok := asMap(v)
		if !ok {
			return verr("$.pressure.model_costs", "must be a mapping of model to USD per 1M tokens")
		}
		for model, cv := range costs {
			n, ok := asFloat(cv)
			if !ok {
				return verr("$.pressure.model_costs."+model, "expected number, got %T", cv)
			}
			if n < 0 {
				return verr("$.pressure.model_costs."+model, "must be non-negative (got %v)", n)
			}
		}
	}
	if v, present := p["budget_usd"]; present {
		n, ok := asFloat(v)
		if !ok {
			return verr("$.pressure.budget_usd", "expected number, got %T", v)
		}
		if n < 0 {
			return verr("$.pressure.budget_usd", "must be non-negative (got %v)", n)
		}
	}
	return nil
}

func validateCoordinator(root map[string]any) error {
	raw, present := root["coordinator"]
	if !present {
		return nil
	}
	c, ok := asMap(raw)
	if !ok {
		return verr("$.coordinator", "must be a mapping")
	}
	if v, present := c["aggregator"]; present {
		s, ok := v.(string)
		if !ok || !knownAggregators[s] {
			return verr("$.coordinator.aggregator",
				"must be one of sum|mean|max|weighted_sum (got %v)", v)
		}
	}
	for _, f := range []string{"escalation_threshold", "release_threshold", "notify_cooldown_seconds"} {
		v, present := c[f]
		if !present {
			continue
		}
		n, ok := asFloat(v)
		if !ok {
			return verr("$.coordinator."+f, "expected number, got %T", v)
		}
		if n < 0 {
			return verr("$.coordinator."+f, "must be non-negative (got %v)", n)
		}
	}
	esc, hasEsc := asFloat(c["escalation_threshold"])
	rel, hasRel := asFloat(c["release_threshold"])
	if hasEsc && hasRel && rel <= esc {
		return verr("$.coordinator.release_threshold",
			"must exceed escalation_threshold (%v <= %v)", rel, esc)
	}
	if v, present := c["weights"]; present {
		w, ok := asMap(v)
		if !ok {
			return verr("$.coordinator.weights", "must be a mapping")
		}
		for k, wv := range w {
			if _, ok := asFloat(wv); !ok {
				return verr("$.coordinator.weights."+k, "expected number, got %T", wv)
			}
		}
	}
	if v, present := c["default_weight"]; present {
		if _, ok := asFloat(v); !ok {
			return verr("$.coordinator.default_weight", "expected number, got %T", v)
		}
	}
	return nil
}

func validateConsent(root map[string]any) error {
	raw, present := root["consent"]
	if !present {
		return nil
	}
	c, ok := asMap(raw)
	if !ok {
		return verr("$.consent", "must be a mapping")
	}
	if v, present := c["issuer"]; present {
		s, ok := v.(string)
		if !ok || s == "" {
			return verr("$.consent.issuer", "expected non-empty string")
		}
	}
	if v, present := c["default_ttl_seconds"]; present {
		n, ok := asFloat(v)
		if !ok {
			return verr("$.consent.default_ttl_seconds", "expected number, got %T", v)
		}
		if n < 0 {
			return verr("$.consent.default_ttl_seconds", "must be non-negative (got %v)", n)
		}
	}
	if v, present := c["required_scopes"]; present {
		arr, ok := v.([]any)
		if !ok {
			return verr("$.consent.required_scopes", "expected list")
		}
		for i, item := range arr {
			s, ok := item.(string)
			if !ok || !consent.ValidScopeString(s) {
				return verr(fmt.Sprintf("$.consent.required_scopes[%d]", i),
					"%v is not a valid scope", item)
			}
		}
	}
	if v, present := c["allowed_algorithms"]; present {
		arr, ok := v.([]any)
		if !ok {
			return verr("$.consent.allowed_algorithms", "expected list")
		}
		for i, item := range arr {
			if _, ok := item.(string); !ok {
				return verr(fmt.Sprintf("$.consent.allowed_algorithms[%d]", i), "expected string")
			}
		}
	}
	return nil
}
