package core

import (
	"errors"
	"strings"
	"testing"
)

func TestConfigValidation(t *testing.T) {
	cases := []struct {
		name    string
		mutate  func(*PressureConfig)
		wantSub string
	}{
		{"default is valid", func(*PressureConfig) {}, ""},
		{"release below escalation", func(c *PressureConfig) {
			c.EscalationThreshold, c.ReleaseThreshold = 0.9, 0.5
		}, "release_threshold must exceed escalation_threshold"},
		{"negative token coefficient", func(c *PressureConfig) {
			c.TokenCoefficient = -0.01
		}, "token_coefficient"},
		{"threshold out of range", func(c *PressureConfig) {
			c.EscalationThreshold = 1.5
		}, "escalation_threshold"},
		{"negative budget", func(c *PressureConfig) { c.BudgetUSD = -1 }, "budget_usd"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			cfg := DefaultConfig()
			tc.mutate(&cfg)
			err := cfg.Validate()
			if tc.wantSub == "" {
				if err != nil {
					t.Fatalf("unexpected error: %v", err)
				}
				return
			}
			if err == nil {
				t.Fatal("expected an error, got nil")
			}
			if !errors.Is(err, ErrConfig) {
				t.Fatalf("error does not wrap ErrConfig: %v", err)
			}
			if !strings.Contains(err.Error(), tc.wantSub) {
				t.Fatalf("error %q does not name %q", err, tc.wantSub)
			}
		})
	}
}

func TestConstructorReturnsErrorNeverPanics(t *testing.T) {
	cfg := DefaultConfig()
	cfg.ReleaseThreshold = 0.1
	if _, err := NewPressureEngine(cfg, EngineOptions{}); err == nil {
		t.Fatal("expected a config error")
	}
}
