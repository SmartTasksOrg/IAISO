// Package conformance runs the IAIso spec vectors against this
// implementation.
//
// The vectors are the contract. A port that does not pass every vector is
// not a port; it is a plausible-looking program. RunAll loads
// spec/{pressure,consent,events,policy}/vectors.json and executes all 67.
package conformance

import (
	"fmt"
	"io"
	"log"
	"math"
	"os"
	"path/filepath"

	"github.com/iaiso/iaiso-go/iaiso/core"
)

// The vectors deliberately exercise degraded configurations (NullSink,
// post_release_lock=false, uncalibrated defaults). Their permissive-mode
// warnings are expected, and printing them would corrupt the suite's
// output. Silence them for the duration of a run only.
func silenceWarnings() func() {
	prev := core.WarnLogger
	core.WarnLogger = log.New(io.Discard, "", 0)
	return func() { core.WarnLogger = prev }
}

// Result is the outcome of a single vector.
type Result struct {
	Section string
	Name    string
	Passed  bool
	Message string
}

// Results groups vector results by section. cmd/iaiso-conformance indexes
// it by section name and calls CountPassed, so both are part of the
// package's fixed public surface.
type Results map[string][]Result

// Sections in the order the CLI prints them.
var Sections = []string{"pressure", "consent", "events", "policy"}

// CountPassed returns (passed, total) across every section.
func (r Results) CountPassed() (int, int) {
	pass, total := 0, 0
	for _, section := range Sections {
		for _, v := range r[section] {
			total++
			if v.Passed {
				pass++
			}
		}
	}
	return pass, total
}

// Failures returns every result that did not pass.
func (r Results) Failures() []Result {
	var out []Result
	for _, section := range Sections {
		for _, v := range r[section] {
			if !v.Passed {
				out = append(out, v)
			}
		}
	}
	return out
}

// RunAll executes every vector under specRoot.
//
// specRoot is the directory containing pressure/, consent/, events/ and
// policy/ — i.e. `./spec`, not `./spec/pressure`.
func RunAll(specRoot string) (Results, error) {
	if fi, err := os.Stat(specRoot); err != nil || !fi.IsDir() {
		return nil, fmt.Errorf("conformance: spec root %q is not a directory", specRoot)
	}
	defer silenceWarnings()()
	results := Results{}

	pressure, err := runPressure(specRoot)
	if err != nil {
		return nil, err
	}
	results["pressure"] = pressure

	consentResults, err := runConsent(specRoot)
	if err != nil {
		return nil, err
	}
	results["consent"] = consentResults

	events, err := runEvents(specRoot)
	if err != nil {
		return nil, err
	}
	results["events"] = events

	policyResults, err := runPolicy(specRoot)
	if err != nil {
		return nil, err
	}
	results["policy"] = policyResults

	return results, nil
}

func vectorPath(specRoot, section string) string {
	return filepath.Join(specRoot, section, "vectors.json")
}

func readVectors(specRoot, section string) ([]byte, error) {
	p := vectorPath(specRoot, section)
	b, err := os.ReadFile(p)
	if err != nil {
		return nil, fmt.Errorf("conformance: read %s: %w", p, err)
	}
	return b, nil
}

// floatClose compares against the tolerance declared in the vector file.
// The spec is written in real-number semantics; `==` on IEEE-754 doubles
// would fail vectors that are arithmetically correct.
func floatClose(a, b, tolerance float64) bool {
	if math.IsNaN(a) || math.IsNaN(b) {
		return math.IsNaN(a) && math.IsNaN(b)
	}
	return math.Abs(a-b) <= tolerance
}

func pass(section, name string) Result {
	return Result{Section: section, Name: name, Passed: true}
}

func fail(section, name, format string, args ...any) Result {
	return Result{
		Section: section, Name: name, Passed: false,
		Message: fmt.Sprintf(format, args...),
	}
}

func sprintf(format string, args ...any) string { return fmt.Sprintf(format, args...) }
