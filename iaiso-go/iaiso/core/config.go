package core

import (
	"errors"
	"fmt"
)

// ErrConfig is the sentinel wrapped by every configuration error, so callers
// can branch with errors.Is(err, core.ErrConfig) instead of string matching.
var ErrConfig = errors.New("config error")

// ConfigError describes a single validation failure. Field names the
// offending key; the message always contains that name, which is what the
// spec/pressure/vectors.json `expect_config_error` cases assert on.
type ConfigError struct {
	Field   string
	Message string
}

func (e *ConfigError) Error() string { return e.Message }
func (e *ConfigError) Unwrap() error { return ErrConfig }

func cfgErr(field, format string, args ...any) *ConfigError {
	return &ConfigError{Field: field, Message: fmt.Sprintf(format, args...)}
}

// Default coefficients. These are PLACEHOLDERS, not recommendations.
// Thresholds that have not been calibrated against your workload will
// either never fire or fire constantly. See LIMITATIONS.md §4.2.
const (
	DefaultEscalationThreshold  = 0.85
	DefaultReleaseThreshold     = 0.95
	DefaultDissipationPerStep   = 0.02
	DefaultDissipationPerSecond = 0.0
	DefaultTokenCoefficient     = 0.015 // per 1000 tokens
	DefaultToolCoefficient      = 0.08
	DefaultDepthCoefficient     = 0.05
	DefaultPostReleaseLock      = true
)

// PressureConfig parameterises the pressure engine.
//
// Pressure is the SAFETY control. Spend (ModelCosts, BudgetUSD) is a FINANCE
// readout carried alongside it. They are deliberately separate: conflating
// them is how you end up with a safety threshold tuned by a CFO.
type PressureConfig struct {
	EscalationThreshold  float64 // [0,1]
	ReleaseThreshold     float64 // [0,1], MUST be > EscalationThreshold
	DissipationPerStep   float64 // >= 0
	DissipationPerSecond float64 // >= 0
	TokenCoefficient     float64 // >= 0, applied per 1000 tokens
	ToolCoefficient      float64 // >= 0
	DepthCoefficient     float64 // >= 0
	PostReleaseLock      bool

	// ModelCosts maps a model identifier to USD per 1,000,000 tokens.
	// When non-empty the engine additionally tracks spend_usd and adds it
	// to the engine.step payload. Pressure remains the control signal.
	// Optional (WI-5); absent by default so the wire format is unchanged.
	ModelCosts map[string]float64

	// BudgetUSD is an optional hard ceiling per execution, independent of
	// pressure. Zero means unlimited. When exceeded the engine takes the
	// lock path — no new lifecycle state is introduced.
	BudgetUSD float64
}

// DefaultConfig returns the library defaults. Calibrate before relying on
// specific threshold values.
func DefaultConfig() PressureConfig {
	return PressureConfig{
		EscalationThreshold:  DefaultEscalationThreshold,
		ReleaseThreshold:     DefaultReleaseThreshold,
		DissipationPerStep:   DefaultDissipationPerStep,
		DissipationPerSecond: DefaultDissipationPerSecond,
		TokenCoefficient:     DefaultTokenCoefficient,
		ToolCoefficient:      DefaultToolCoefficient,
		DepthCoefficient:     DefaultDepthCoefficient,
		PostReleaseLock:      DefaultPostReleaseLock,
	}
}

// IsDefaultCoefficients reports whether every coefficient and threshold is
// still at its library default. Used by the enforcement_mode boot guard.
func (c PressureConfig) IsDefaultCoefficients() bool {
	d := DefaultConfig()
	return c.EscalationThreshold == d.EscalationThreshold &&
		c.ReleaseThreshold == d.ReleaseThreshold &&
		c.DissipationPerStep == d.DissipationPerStep &&
		c.DissipationPerSecond == d.DissipationPerSecond &&
		c.TokenCoefficient == d.TokenCoefficient &&
		c.ToolCoefficient == d.ToolCoefficient &&
		c.DepthCoefficient == d.DepthCoefficient
}

// Validate checks the config for internal consistency. It returns an error
// rather than panicking, mirroring ConfigError in the Python and Rust ports.
func (c PressureConfig) Validate() error {
	if c.EscalationThreshold < 0 || c.EscalationThreshold > 1 {
		return cfgErr("escalation_threshold",
			"escalation_threshold must be in [0, 1], got %v", c.EscalationThreshold)
	}
	if c.ReleaseThreshold < 0 || c.ReleaseThreshold > 1 {
		return cfgErr("release_threshold",
			"release_threshold must be in [0, 1], got %v", c.ReleaseThreshold)
	}
	if c.ReleaseThreshold <= c.EscalationThreshold {
		return cfgErr("release_threshold",
			"release_threshold must exceed escalation_threshold (%v <= %v)",
			c.ReleaseThreshold, c.EscalationThreshold)
	}
	for _, f := range []struct {
		name string
		v    float64
	}{
		{"token_coefficient", c.TokenCoefficient},
		{"tool_coefficient", c.ToolCoefficient},
		{"depth_coefficient", c.DepthCoefficient},
		{"dissipation_per_step", c.DissipationPerStep},
		{"dissipation_per_second", c.DissipationPerSecond},
	} {
		if f.v < 0 {
			return cfgErr(f.name, "%s must be non-negative, got %v", f.name, f.v)
		}
	}
	if c.BudgetUSD < 0 {
		return cfgErr("budget_usd", "budget_usd must be non-negative, got %v", c.BudgetUSD)
	}
	for model, cost := range c.ModelCosts {
		if cost < 0 {
			return cfgErr("model_costs",
				"model_costs[%q] must be non-negative, got %v", model, cost)
		}
	}
	return nil
}
