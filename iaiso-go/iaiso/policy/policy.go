package policy

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	goyaml "github.com/goccy/go-yaml"
	"github.com/iaiso/iaiso-go/iaiso/core"
)

// AggregatorKind names a fleet-pressure aggregation strategy. Wire-format
// strings; shared with the coordinator spec.
type AggregatorKind string

const (
	AggregatorSum         AggregatorKind = "sum"
	AggregatorMean        AggregatorKind = "mean"
	AggregatorMax         AggregatorKind = "max"
	AggregatorWeightedSum AggregatorKind = "weighted_sum"
)

// Aggregator combines per-execution pressures into one fleet number.
type Aggregator interface {
	Name() AggregatorKind
	Aggregate(pressures map[string]float64) float64
}

// SumAggregator adds every pressure. This is what stops a hundred agents
// from each spending "just under" a per-agent cap.
type SumAggregator struct{}

func (SumAggregator) Name() AggregatorKind { return AggregatorSum }
func (SumAggregator) Aggregate(p map[string]float64) float64 {
	var t float64
	for _, v := range p {
		t += v
	}
	return t
}

// MeanAggregator averages. Empty fleet aggregates to 0.
type MeanAggregator struct{}

func (MeanAggregator) Name() AggregatorKind { return AggregatorMean }
func (MeanAggregator) Aggregate(p map[string]float64) float64 {
	if len(p) == 0 {
		return 0
	}
	var t float64
	for _, v := range p {
		t += v
	}
	return t / float64(len(p))
}

// MaxAggregator takes the loudest worker.
type MaxAggregator struct{}

func (MaxAggregator) Name() AggregatorKind { return AggregatorMax }
func (MaxAggregator) Aggregate(p map[string]float64) float64 {
	m := 0.0
	for _, v := range p {
		if v > m {
			m = v
		}
	}
	return m
}

// WeightedSumAggregator prices some executions higher than others.
type WeightedSumAggregator struct {
	Weights       map[string]float64
	DefaultWeight float64
}

func (WeightedSumAggregator) Name() AggregatorKind { return AggregatorWeightedSum }
func (a WeightedSumAggregator) Aggregate(p map[string]float64) float64 {
	var t float64
	keys := make([]string, 0, len(p))
	for k := range p {
		keys = append(keys, k)
	}
	sort.Strings(keys) // deterministic float summation order
	for _, k := range keys {
		w, ok := a.Weights[k]
		if !ok {
			w = a.DefaultWeight
		}
		t += w * p[k]
	}
	return t
}

// CoordinatorConfig is the coordinator section of a policy file. Its
// thresholds are fleet-wide sums, so they are not bounded by [0,1].
type CoordinatorConfig struct {
	EscalationThreshold   float64
	ReleaseThreshold      float64
	NotifyCooldownSeconds float64
}

// DefaultCoordinatorConfig returns the library defaults.
func DefaultCoordinatorConfig() CoordinatorConfig {
	return CoordinatorConfig{
		EscalationThreshold:   5.0,
		ReleaseThreshold:      8.0,
		NotifyCooldownSeconds: 1.0,
	}
}

// ConsentPolicy is the consent section of a policy file.
type ConsentPolicy struct {
	// Issuer is nil when the policy does not set one.
	Issuer            *string
	DefaultTTLSeconds float64
	RequiredScopes    []string
	AllowedAlgorithms []string
}

// DefaultConsentPolicy returns the library defaults.
func DefaultConsentPolicy() ConsentPolicy {
	return ConsentPolicy{
		Issuer:            nil,
		DefaultTTLSeconds: 3600.0,
		RequiredScopes:    []string{},
		AllowedAlgorithms: []string{"HS256", "RS256"},
	}
}

// Policy is an assembled, validated policy document.
type Policy struct {
	Version         string
	EnforcementMode string
	Pressure        core.PressureConfig
	Coordinator     CoordinatorConfig
	Consent         ConsentPolicy
	Aggregator      Aggregator
	Metadata        map[string]any
}

// Build validates doc and assembles a Policy, filling every unset section
// with its default. Unknown keys — top-level or nested — are ignored, so a
// policy written for a newer IAIso still loads.
func Build(doc any) (*Policy, error) {
	if err := Validate(doc); err != nil {
		return nil, err
	}
	root, _ := asMap(doc)

	p := &Policy{
		Version:         SchemaVersion,
		EnforcementMode: core.EnforcementPermissive,
		Pressure:        core.DefaultConfig(),
		Coordinator:     DefaultCoordinatorConfig(),
		Consent:         DefaultConsentPolicy(),
		Aggregator:      SumAggregator{},
		Metadata:        map[string]any{},
	}

	if v, ok := root["enforcement_mode"].(string); ok {
		p.EnforcementMode = v
	}

	if pm, ok := asMap(root["pressure"]); ok {
		setFloat(pm, "token_coefficient", &p.Pressure.TokenCoefficient)
		setFloat(pm, "tool_coefficient", &p.Pressure.ToolCoefficient)
		setFloat(pm, "depth_coefficient", &p.Pressure.DepthCoefficient)
		setFloat(pm, "dissipation_per_step", &p.Pressure.DissipationPerStep)
		setFloat(pm, "dissipation_per_second", &p.Pressure.DissipationPerSecond)
		setFloat(pm, "escalation_threshold", &p.Pressure.EscalationThreshold)
		setFloat(pm, "release_threshold", &p.Pressure.ReleaseThreshold)
		setFloat(pm, "budget_usd", &p.Pressure.BudgetUSD)
		if b, ok := pm["post_release_lock"].(bool); ok {
			p.Pressure.PostReleaseLock = b
		}
		if mc, ok := asMap(pm["model_costs"]); ok && len(mc) > 0 {
			p.Pressure.ModelCosts = map[string]float64{}
			for model, cv := range mc {
				if n, ok := asFloat(cv); ok {
					p.Pressure.ModelCosts[model] = n
				}
			}
		}
	}

	if cm, ok := asMap(root["coordinator"]); ok {
		setFloat(cm, "escalation_threshold", &p.Coordinator.EscalationThreshold)
		setFloat(cm, "release_threshold", &p.Coordinator.ReleaseThreshold)
		setFloat(cm, "notify_cooldown_seconds", &p.Coordinator.NotifyCooldownSeconds)

		name, _ := cm["aggregator"].(string)
		switch AggregatorKind(name) {
		case AggregatorMean:
			p.Aggregator = MeanAggregator{}
		case AggregatorMax:
			p.Aggregator = MaxAggregator{}
		case AggregatorWeightedSum:
			weights := map[string]float64{}
			if wm, ok := asMap(cm["weights"]); ok {
				for k, v := range wm {
					if n, ok := asFloat(v); ok {
						weights[k] = n
					}
				}
			}
			def := 1.0
			setFloat(cm, "default_weight", &def)
			p.Aggregator = WeightedSumAggregator{Weights: weights, DefaultWeight: def}
		default:
			p.Aggregator = SumAggregator{}
		}
	}

	if km, ok := asMap(root["consent"]); ok {
		if s, ok := km["issuer"].(string); ok {
			iss := s
			p.Consent.Issuer = &iss
		}
		setFloat(km, "default_ttl_seconds", &p.Consent.DefaultTTLSeconds)
		if arr, ok := km["required_scopes"].([]any); ok {
			scopes := make([]string, 0, len(arr))
			for _, v := range arr {
				if s, ok := v.(string); ok {
					scopes = append(scopes, s)
				}
			}
			p.Consent.RequiredScopes = scopes
		}
		if arr, ok := km["allowed_algorithms"].([]any); ok {
			algs := make([]string, 0, len(arr))
			for _, v := range arr {
				if s, ok := v.(string); ok {
					algs = append(algs, s)
				}
			}
			p.Consent.AllowedAlgorithms = algs
		}
	}

	if md, ok := asMap(root["metadata"]); ok {
		p.Metadata = md
	}

	// The assembled pressure config must still satisfy the engine's own
	// invariants. A policy that passes schema validation but produces an
	// unconstructable engine is a policy that fails at 3am, not at boot.
	if err := p.Pressure.Validate(); err != nil {
		return nil, verr("$.pressure", "%v", err)
	}
	return p, nil
}

func setFloat(m map[string]any, key string, dst *float64) {
	if v, ok := m[key]; ok {
		if n, ok := asFloat(v); ok {
			*dst = n
		}
	}
}

// Load reads a .json, .yaml or .yml policy file and builds it.
func Load(path string) (*Policy, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("%w: read %s: %v", ErrPolicy, path, err)
	}
	return Parse(raw, filepath.Ext(path))
}

// Parse builds a policy from raw bytes. ext is ".json", ".yaml" or ".yml".
func Parse(raw []byte, ext string) (*Policy, error) {
	var doc any
	switch strings.ToLower(ext) {
	case ".json":
		dec := json.NewDecoder(strings.NewReader(string(raw)))
		dec.UseNumber()
		if err := dec.Decode(&doc); err != nil {
			return nil, fmt.Errorf("%w: JSON parse failed: %v", ErrPolicy, err)
		}
	case ".yaml", ".yml":
		if err := goyaml.Unmarshal(raw, &doc); err != nil {
			return nil, fmt.Errorf("%w: YAML parse failed: %v", ErrPolicy, err)
		}
		doc = normalise(doc)
	default:
		return nil, fmt.Errorf("%w: unsupported policy file extension: %s "+
			"(expected .json, .yaml, or .yml)", ErrPolicy, ext)
	}
	return Build(doc)
}

// normalise converts map[any]any (which some YAML decoders emit) into
// map[string]any so validation can walk the document uniformly.
func normalise(v any) any {
	switch t := v.(type) {
	case map[any]any:
		out := make(map[string]any, len(t))
		for k, val := range t {
			out[fmt.Sprint(k)] = normalise(val)
		}
		return out
	case map[string]any:
		out := make(map[string]any, len(t))
		for k, val := range t {
			out[k] = normalise(val)
		}
		return out
	case []any:
		out := make([]any, len(t))
		for i, val := range t {
			out[i] = normalise(val)
		}
		return out
	default:
		return v
	}
}

// Template returns a commented starter policy file.
func Template() string {
	return `{
  "version": "1",
  "enforcement_mode": "permissive",
  "pressure": {
    "token_coefficient": 0.015,
    "tool_coefficient": 0.08,
    "depth_coefficient": 0.05,
    "dissipation_per_step": 0.02,
    "dissipation_per_second": 0.0,
    "escalation_threshold": 0.85,
    "release_threshold": 0.95,
    "post_release_lock": true
  },
  "coordinator": {
    "escalation_threshold": 5.0,
    "release_threshold": 8.0,
    "notify_cooldown_seconds": 1.0,
    "aggregator": "sum"
  },
  "consent": {
    "issuer": "iaiso",
    "default_ttl_seconds": 3600,
    "required_scopes": [],
    "allowed_algorithms": ["HS256", "RS256"]
  },
  "metadata": {
    "environment": "dev",
    "owner": "platform"
  }
}
`
}
