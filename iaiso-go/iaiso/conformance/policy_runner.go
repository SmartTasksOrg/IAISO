package conformance

import (
	"encoding/json"
	"strings"

	"github.com/iaiso/iaiso-go/iaiso/policy"
)

type validPolicyVector struct {
	Name                 string          `json:"name"`
	Description          string          `json:"description"`
	Document             any             `json:"document"`
	ExpectedPressure     map[string]any  `json:"expected_pressure"`
	ExpectedConsent      map[string]any  `json:"expected_consent"`
	ExpectedCoordinator  map[string]any  `json:"expected_coordinator"`
	ExpectedMetadata     map[string]any  `json:"expected_metadata"`
	ExpectedAggregatorNm *string         `json:"expected_aggregator_name"`
	ExpectedEnforcement  *string         `json:"expected_enforcement_mode"`
	ExpectLoads          *bool           `json:"expect_loads"`
	_                    json.RawMessage `json:"-"`
}

type invalidPolicyVector struct {
	Name            string `json:"name"`
	Description     string `json:"description"`
	Document        any    `json:"document"`
	ExpectErrorPath string `json:"expect_error_path"`
}

type policyFile struct {
	Tolerance float64               `json:"tolerance"`
	Valid     []validPolicyVector   `json:"valid"`
	Invalid   []invalidPolicyVector `json:"invalid"`
}

func runPolicy(specRoot string) ([]Result, error) {
	raw, err := readVectors(specRoot, "policy")
	if err != nil {
		return nil, err
	}
	var file policyFile
	if err := json.Unmarshal(raw, &file); err != nil {
		return nil, err
	}
	if file.Tolerance == 0 {
		file.Tolerance = 1e-9
	}

	out := make([]Result, 0, len(file.Valid)+len(file.Invalid))
	for _, v := range file.Valid {
		out = append(out, runOneValidPolicy(v, file.Tolerance))
	}
	for _, v := range file.Invalid {
		out = append(out, runOneInvalidPolicy(v))
	}
	return out, nil
}

func runOneValidPolicy(v validPolicyVector, tol float64) Result {
	const section = "policy"
	name := "valid/" + v.Name

	p, err := policy.Build(v.Document)
	if err != nil {
		return fail(section, name, "build failed: %v", err)
	}

	if v.ExpectedPressure != nil {
		got := map[string]float64{
			"token_coefficient":      p.Pressure.TokenCoefficient,
			"tool_coefficient":       p.Pressure.ToolCoefficient,
			"depth_coefficient":      p.Pressure.DepthCoefficient,
			"dissipation_per_step":   p.Pressure.DissipationPerStep,
			"dissipation_per_second": p.Pressure.DissipationPerSecond,
			"escalation_threshold":   p.Pressure.EscalationThreshold,
			"release_threshold":      p.Pressure.ReleaseThreshold,
		}
		for key, wantAny := range v.ExpectedPressure {
			if key == "post_release_lock" {
				wantB, ok := wantAny.(bool)
				if ok && p.Pressure.PostReleaseLock != wantB {
					return fail(section, name, "post_release_lock: got %v, want %v",
						p.Pressure.PostReleaseLock, wantB)
				}
				continue
			}
			wantF, ok := wantAny.(float64)
			if !ok {
				continue
			}
			gotF, known := got[key]
			if !known {
				return fail(section, name, "unknown expected_pressure key %q", key)
			}
			if !floatClose(gotF, wantF, tol) {
				return fail(section, name, "%s: got %v, want %v", key, gotF, wantF)
			}
		}
	}

	if v.ExpectedCoordinator != nil {
		got := map[string]float64{
			"escalation_threshold":    p.Coordinator.EscalationThreshold,
			"release_threshold":       p.Coordinator.ReleaseThreshold,
			"notify_cooldown_seconds": p.Coordinator.NotifyCooldownSeconds,
		}
		for key, wantAny := range v.ExpectedCoordinator {
			wantF, ok := wantAny.(float64)
			if !ok {
				continue
			}
			gotF, known := got[key]
			if !known {
				return fail(section, name, "unknown expected_coordinator key %q", key)
			}
			if !floatClose(gotF, wantF, tol) {
				return fail(section, name, "coordinator.%s: got %v, want %v", key, gotF, wantF)
			}
		}
	}

	if v.ExpectedConsent != nil {
		if wantIssuer, present := v.ExpectedConsent["issuer"]; present {
			switch want := wantIssuer.(type) {
			case nil:
				if p.Consent.Issuer != nil {
					return fail(section, name, "consent.issuer: got %q, want null", *p.Consent.Issuer)
				}
			case string:
				if p.Consent.Issuer == nil || *p.Consent.Issuer != want {
					return fail(section, name, "consent.issuer: got %v, want %q", p.Consent.Issuer, want)
				}
			}
		}
		if wantTTL, ok := v.ExpectedConsent["default_ttl_seconds"].(float64); ok {
			if !floatClose(p.Consent.DefaultTTLSeconds, wantTTL, tol) {
				return fail(section, name, "consent.default_ttl_seconds: got %v, want %v",
					p.Consent.DefaultTTLSeconds, wantTTL)
			}
		}
		if wantScopes, ok := v.ExpectedConsent["required_scopes"].([]any); ok {
			if len(wantScopes) != len(p.Consent.RequiredScopes) {
				return fail(section, name, "consent.required_scopes: got %v, want %v",
					p.Consent.RequiredScopes, wantScopes)
			}
			for i, s := range wantScopes {
				if str, ok := s.(string); ok && p.Consent.RequiredScopes[i] != str {
					return fail(section, name, "consent.required_scopes[%d]: got %q, want %q",
						i, p.Consent.RequiredScopes[i], str)
				}
			}
		}
		if wantAlgs, ok := v.ExpectedConsent["allowed_algorithms"].([]any); ok {
			if len(wantAlgs) != len(p.Consent.AllowedAlgorithms) {
				return fail(section, name, "consent.allowed_algorithms: got %v, want %v",
					p.Consent.AllowedAlgorithms, wantAlgs)
			}
		}
	}

	if v.ExpectedEnforcement != nil {
		if p.EnforcementMode != *v.ExpectedEnforcement {
			return fail(section, name, "enforcement_mode: got %q, want %q",
				p.EnforcementMode, *v.ExpectedEnforcement)
		}
	}

	if v.ExpectedAggregatorNm != nil {
		if string(p.Aggregator.Name()) != *v.ExpectedAggregatorNm {
			return fail(section, name, "aggregator: got %q, want %q",
				p.Aggregator.Name(), *v.ExpectedAggregatorNm)
		}
	}

	if v.ExpectedMetadata != nil {
		if len(p.Metadata) != len(v.ExpectedMetadata) {
			return fail(section, name, "metadata size: got %d, want %d",
				len(p.Metadata), len(v.ExpectedMetadata))
		}
		for k, want := range v.ExpectedMetadata {
			got, present := p.Metadata[k]
			if !present {
				return fail(section, name, "metadata missing key %q", k)
			}
			if got != want {
				return fail(section, name, "metadata[%q]: got %v, want %v", k, got, want)
			}
		}
	}
	return pass(section, name)
}

func runOneInvalidPolicy(v invalidPolicyVector) Result {
	const section = "policy"
	name := "invalid/" + v.Name

	_, err := policy.Build(v.Document)
	if err == nil {
		return fail(section, name, "expected error containing %q, got nil", v.ExpectErrorPath)
	}
	if !strings.Contains(err.Error(), v.ExpectErrorPath) {
		return fail(section, name, "expected error containing %q, got %q",
			v.ExpectErrorPath, err.Error())
	}
	return pass(section, name)
}
