package core

import (
	"fmt"
	"log"
	"strings"
	"sync"

	"github.com/iaiso/iaiso-go/iaiso/audit"
)

// Enforcement modes. A deployment's safety posture should be visible at
// runtime; an operator must be able to tell whether a gate is doing
// anything. See LIMITATIONS.md and spec/policy/README.md.
const (
	// EnforcementPermissive is the default: degraded conditions are logged
	// once per process at WARN and construction proceeds.
	EnforcementPermissive = "permissive"
	// EnforcementStrict refuses to construct the engine when any gate would
	// silently do nothing. Fail closed. A safety framework whose gates
	// silently do nothing is worse than no framework, because it produces
	// confidence.
	EnforcementStrict = "strict"
)

// ErrStrictMode is wrapped by every strict-mode boot failure.
var ErrStrictMode = fmt.Errorf("iaiso: strict mode")

// StrictModeError names the failing condition. The message always tells the
// operator both what failed and how to proceed.
type StrictModeError struct {
	Condition string
	Message   string
}

func (e *StrictModeError) Error() string { return e.Message }
func (e *StrictModeError) Unwrap() error { return ErrStrictMode }

// WarnLogger receives permissive-mode degradation warnings. Point it at
// your structured logger, or at io.Discard in tests. It is deliberately not
// nil-able to silence: a safety warning that goes nowhere by default is the
// bug this package exists to prevent.
var WarnLogger = log.Default()

var warnOnce sync.Map // condition -> *sync.Once

func warnDegraded(condition, msg string) {
	v, _ := warnOnce.LoadOrStore(condition, &sync.Once{})
	v.(*sync.Once).Do(func() {
		if WarnLogger != nil {
			WarnLogger.Printf("WARN iaiso: %s", msg)
		}
	})
}

// degradation is one boot-guard condition.
type degradation struct {
	condition string
	message   string
}

// BootGuard applies the enforcement_mode contract at engine construction.
//
// In permissive mode each degraded condition is logged once per process and
// construction proceeds. In strict mode the first degraded condition aborts
// construction with a *StrictModeError naming it.
//
// The consent-side condition from the spec — HS256 with an auto-generated
// signing key — is enforced in consent.NewIssuer/NewVerifier, which are the
// only places that know whether a key was supplied or generated.
func BootGuard(cfg PressureConfig, opts EngineOptions) error {
	mode := strings.ToLower(strings.TrimSpace(opts.EnforcementMode))
	if mode == "" {
		mode = EnforcementPermissive
	}
	if mode != EnforcementPermissive && mode != EnforcementStrict {
		return cfgErr("enforcement_mode",
			"enforcement_mode must be %q or %q, got %q",
			EnforcementPermissive, EnforcementStrict, opts.EnforcementMode)
	}

	var found []degradation

	if isNullSink(opts.Sink) {
		found = append(found, degradation{
			condition: "null_audit_sink",
			message: "audit sink is NullSink; escalations would be unobservable. " +
				"Configure a sink or set enforcement_mode: permissive.",
		})
	}
	if !cfg.PostReleaseLock {
		found = append(found, degradation{
			condition: "post_release_lock_disabled",
			message: "post_release_lock is false; a released execution resumes immediately. " +
				"Set post_release_lock: true or set enforcement_mode: permissive.",
		})
	}
	if cfg.IsDefaultCoefficients() && opts.CalibrationArtifact == "" {
		found = append(found, degradation{
			condition: "uncalibrated_defaults",
			message: "coefficients are at library defaults and no calibration artifact is present; " +
				"thresholds will either never fire or fire constantly. " +
				"Calibrate, or set enforcement_mode: permissive.",
		})
	}

	if mode == EnforcementStrict {
		if len(found) > 0 {
			d := found[0]
			return &StrictModeError{
				Condition: d.condition,
				Message:   "iaiso: strict mode — " + d.message,
			}
		}
		return nil
	}

	for _, d := range found {
		warnDegraded(d.condition, d.message)
	}
	return nil
}

func isNullSink(s audit.Sink) bool {
	if s == nil {
		return true
	}
	_, ok := s.(*audit.NullSink)
	return ok
}
