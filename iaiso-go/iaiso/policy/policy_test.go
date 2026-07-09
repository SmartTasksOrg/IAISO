package policy

import (
	"strings"
	"testing"
)

func mustParse(t *testing.T, raw, ext string) *Policy {
	t.Helper()
	p, err := Parse([]byte(raw), ext)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	return p
}

func TestMinimalPolicyGetsDefaults(t *testing.T) {
	p := mustParse(t, `{"version":"1"}`, ".json")
	if p.Pressure.EscalationThreshold != 0.85 || p.Pressure.ReleaseThreshold != 0.95 {
		t.Fatalf("defaults not applied: %+v", p.Pressure)
	}
	if p.EnforcementMode != "permissive" {
		t.Fatalf("enforcement_mode = %q, want permissive", p.EnforcementMode)
	}
	if p.Aggregator.Name() != AggregatorSum {
		t.Fatalf("aggregator = %q, want sum", p.Aggregator.Name())
	}
}

func TestYAMLAndJSONAgree(t *testing.T) {
	j := mustParse(t, `{"version":"1","pressure":{"token_coefficient":0.02}}`, ".json")
	y := mustParse(t, "version: \"1\"\npressure:\n  token_coefficient: 0.02\n", ".yaml")
	if j.Pressure.TokenCoefficient != y.Pressure.TokenCoefficient {
		t.Fatalf("json %v != yaml %v", j.Pressure.TokenCoefficient, y.Pressure.TokenCoefficient)
	}
}

func TestUnknownKeysAreIgnored(t *testing.T) {
	// Forward compatibility: a policy written for a newer IAIso must load.
	if _, err := Parse([]byte(`{"version":"1","future_section":{"x":1}}`), ".json"); err != nil {
		t.Fatalf("unknown key rejected: %v", err)
	}
}

func TestReleaseMustExceedEscalation(t *testing.T) {
	_, err := Parse([]byte(`{"version":"1","pressure":{"escalation_threshold":0.9,"release_threshold":0.5}}`), ".json")
	if err == nil || !strings.Contains(err.Error(), "$.pressure.release_threshold") {
		t.Fatalf("want a $.pressure.release_threshold error, got %v", err)
	}
}

func TestNumericStringIsATypeErrorNotACoercion(t *testing.T) {
	// Silently coercing "0.015" would hide a typo in a safety-critical file.
	_, err := Parse([]byte(`{"version":"1","pressure":{"token_coefficient":"0.015"}}`), ".json")
	if err == nil || !strings.Contains(err.Error(), "token_coefficient") {
		t.Fatalf("want a token_coefficient type error, got %v", err)
	}
}

func TestWrongVersionIsRejected(t *testing.T) {
	if _, err := Parse([]byte(`{"version":"2"}`), ".json"); err == nil {
		t.Fatal("accepted an unknown schema version")
	}
	if _, err := Parse([]byte(`{}`), ".json"); err == nil {
		t.Fatal("accepted a document with no version")
	}
}

func TestTemplateIsItselfValid(t *testing.T) {
	if _, err := Parse([]byte(Template()), ".json"); err != nil {
		t.Fatalf("the shipped template does not validate: %v", err)
	}
}

func TestAggregators(t *testing.T) {
	p := map[string]float64{"a": 0.2, "b": 0.5, "c": 0.3}
	if got := (SumAggregator{}).Aggregate(p); got < 0.999 || got > 1.001 {
		t.Fatalf("sum = %v", got)
	}
	if got := (MaxAggregator{}).Aggregate(p); got != 0.5 {
		t.Fatalf("max = %v", got)
	}
	if got := (MeanAggregator{}).Aggregate(p); got < 0.333 || got > 0.334 {
		t.Fatalf("mean = %v", got)
	}
	if got := (MeanAggregator{}).Aggregate(map[string]float64{}); got != 0 {
		t.Fatalf("mean of empty fleet = %v, want 0", got)
	}
	w := WeightedSumAggregator{Weights: map[string]float64{"a": 2.0}, DefaultWeight: 1.0}
	if got := w.Aggregate(p); got < 1.199 || got > 1.201 {
		t.Fatalf("weighted_sum = %v, want 1.2", got)
	}
}

func TestUnsupportedExtension(t *testing.T) {
	if _, err := Parse([]byte(`{}`), ".toml"); err == nil {
		t.Fatal("accepted a .toml policy")
	}
}

func TestEnforcementModeParsing(t *testing.T) {
	if p := mustParse(t, `{"version":"1"}`, ".json"); p.EnforcementMode != "permissive" {
		t.Fatalf("absent enforcement_mode = %q, want permissive", p.EnforcementMode)
	}
	if p := mustParse(t, `{"version":"1","enforcement_mode":"strict"}`, ".json"); p.EnforcementMode != "strict" {
		t.Fatalf("enforcement_mode = %q, want strict", p.EnforcementMode)
	}
}

func TestUnknownEnforcementModeIsRejected(t *testing.T) {
	// An unknown mode must not silently degrade to permissive: that is how a
	// deployment ends up believing it is strict when it is not.
	_, err := Parse([]byte(`{"version":"1","enforcement_mode":"advisory"}`), ".json")
	if err == nil || !strings.Contains(err.Error(), "$.enforcement_mode") {
		t.Fatalf("want $.enforcement_mode error, got %v", err)
	}
}

func TestEnforcementModeWrongTypeIsRejected(t *testing.T) {
	_, err := Parse([]byte(`{"version":"1","enforcement_mode":1}`), ".json")
	if err == nil || !strings.Contains(err.Error(), "enforcement_mode") {
		t.Fatalf("want enforcement_mode type error, got %v", err)
	}
}
