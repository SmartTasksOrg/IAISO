package core

import (
	"errors"
	"strings"
	"testing"

	"github.com/iaiso/iaiso-go/iaiso/audit"
)

func strictOpts(sink audit.Sink) EngineOptions {
	return EngineOptions{ExecutionID: "t", Sink: sink, EnforcementMode: EnforcementStrict}
}

func calibrated() PressureConfig {
	cfg := DefaultConfig()
	cfg.TokenCoefficient = 0.011 // not a library default
	return cfg
}

func TestStrictModeRefusesNullSink(t *testing.T) {
	_, err := NewPressureEngine(calibrated(), strictOpts(audit.NewNullSink()))
	if err == nil {
		t.Fatal("strict mode accepted a NullSink")
	}
	if !errors.Is(err, ErrStrictMode) {
		t.Fatalf("error does not wrap ErrStrictMode: %v", err)
	}
	if !strings.Contains(err.Error(), "NullSink") {
		t.Fatalf("error must name the failing condition, got %q", err)
	}
}

func TestStrictModeRefusesPostReleaseLockDisabled(t *testing.T) {
	cfg := calibrated()
	cfg.PostReleaseLock = false
	_, err := NewPressureEngine(cfg, strictOpts(audit.NewMemorySink()))
	if err == nil || !strings.Contains(err.Error(), "post_release_lock") {
		t.Fatalf("want post_release_lock failure, got %v", err)
	}
}

func TestStrictModeRefusesUncalibratedDefaults(t *testing.T) {
	_, err := NewPressureEngine(DefaultConfig(), strictOpts(audit.NewMemorySink()))
	if err == nil || !strings.Contains(err.Error(), "calibration") {
		t.Fatalf("want calibration failure, got %v", err)
	}
}

func TestStrictModeAcceptsCalibrationArtifact(t *testing.T) {
	opts := strictOpts(audit.NewMemorySink())
	opts.CalibrationArtifact = "calibration/2026-07-01.json"
	if _, err := NewPressureEngine(DefaultConfig(), opts); err != nil {
		t.Fatalf("strict mode rejected a calibrated default config: %v", err)
	}
}

func TestStrictModeAcceptsAGoodConfig(t *testing.T) {
	if _, err := NewPressureEngine(calibrated(), strictOpts(audit.NewMemorySink())); err != nil {
		t.Fatalf("strict mode rejected a sound config: %v", err)
	}
}

func TestPermissiveModeIsTheDefaultAndProceeds(t *testing.T) {
	if _, err := NewPressureEngine(DefaultConfig(), EngineOptions{ExecutionID: "t"}); err != nil {
		t.Fatalf("permissive mode refused to construct: %v", err)
	}
}

func TestUnknownEnforcementModeIsAConfigError(t *testing.T) {
	opts := EngineOptions{ExecutionID: "t", EnforcementMode: "advisory"}
	_, err := NewPressureEngine(calibrated(), opts)
	if err == nil || !strings.Contains(err.Error(), "enforcement_mode") {
		t.Fatalf("want enforcement_mode error, got %v", err)
	}
}
