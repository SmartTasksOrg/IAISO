// Package cli implements the `iaiso` admin command.
package cli

import (
	"bufio"
	"context"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"

	"github.com/iaiso/iaiso-go/iaiso/audit"
	"github.com/iaiso/iaiso-go/iaiso/conformance"
	"github.com/iaiso/iaiso-go/iaiso/consent"
	"github.com/iaiso/iaiso-go/iaiso/coordination"
	"github.com/iaiso/iaiso-go/iaiso/policy"
)

const usage = `iaiso — IAIso admin CLI

Usage:
  iaiso policy validate <file.json|file.yaml>
  iaiso policy template [<file>]
  iaiso consent issue <subject> <scope,scope,...> [ttl_seconds]
  iaiso consent verify <token> [execution_id]
  iaiso audit tail <file.jsonl> [n]
  iaiso audit stats <file.jsonl>
  iaiso audit spend <file.jsonl> [--group-by tag|execution_id]
  iaiso coordinator demo
  iaiso conformance <spec_dir>
  iaiso --help

Environment:
  IAISO_HS256_SECRET   signing/verification secret for `+"`consent`"+` subcommands

Notes:
  Pressure is the safety control; spend is the finance readout. `+"`audit spend`"+`
  reports what an execution cost; it does not change what it is allowed to do.
`

// Main is the CLI entry point. It returns the process exit code and never
// calls os.Exit, so it stays testable.
func Main(args []string) int {
	if len(args) == 0 {
		fmt.Print(usage)
		return 0
	}
	switch args[0] {
	case "-h", "--help", "help":
		fmt.Print(usage)
		return 0
	case "--version", "version":
		fmt.Println("iaiso-go SDK 0.2.0 (spec 1.0)")
		return 0
	case "policy":
		return cmdPolicy(args[1:])
	case "consent":
		return cmdConsent(args[1:])
	case "audit":
		return cmdAudit(args[1:])
	case "coordinator":
		return cmdCoordinator(args[1:])
	case "conformance":
		return cmdConformance(args[1:])
	default:
		errf("unknown command %q", args[0])
		fmt.Print(usage)
		return 2
	}
}

func errf(format string, args ...any) {
	fmt.Fprintf(os.Stderr, "iaiso: "+format+"\n", args...)
}

func cmdPolicy(args []string) int {
	if len(args) == 0 {
		errf("policy: expected 'validate' or 'template'")
		return 2
	}
	switch args[0] {
	case "validate":
		if len(args) < 2 {
			errf("policy validate: expected a file path")
			return 2
		}
		p, err := policy.Load(args[1])
		if err != nil {
			errf("%v", err)
			return 1
		}
		fmt.Printf("OK %s\n", args[1])
		fmt.Printf("  version:              %s\n", p.Version)
		fmt.Printf("  enforcement_mode:     %s\n", p.EnforcementMode)
		fmt.Printf("  escalation_threshold: %v\n", p.Pressure.EscalationThreshold)
		fmt.Printf("  release_threshold:    %v\n", p.Pressure.ReleaseThreshold)
		fmt.Printf("  post_release_lock:    %v\n", p.Pressure.PostReleaseLock)
		fmt.Printf("  aggregator:           %s\n", p.Aggregator.Name())
		if p.Pressure.IsDefaultCoefficients() {
			fmt.Println("  note: coefficients are at library defaults — calibrate before " +
				"relying on specific threshold values")
		}
		return 0
	case "template":
		if len(args) < 2 {
			fmt.Print(policy.Template())
			return 0
		}
		if err := os.WriteFile(args[1], []byte(policy.Template()), 0o644); err != nil {
			errf("%v", err)
			return 1
		}
		fmt.Printf("wrote %s\n", args[1])
		return 0
	default:
		errf("policy: unknown subcommand %q", args[0])
		return 2
	}
}

func hs256Secret() ([]byte, bool) {
	s := os.Getenv("IAISO_HS256_SECRET")
	if s == "" {
		errf("IAISO_HS256_SECRET is not set")
		return nil, false
	}
	return []byte(s), true
}

func cmdConsent(args []string) int {
	if len(args) == 0 {
		errf("consent: expected 'issue' or 'verify'")
		return 2
	}
	key, ok := hs256Secret()
	if !ok {
		return 1
	}

	switch args[0] {
	case "issue":
		if len(args) < 3 {
			errf("consent issue: expected <subject> <scopes> [ttl_seconds]")
			return 2
		}
		var ttl int64
		if len(args) >= 4 {
			n, err := strconv.ParseInt(args[3], 10, 64)
			if err != nil {
				errf("consent issue: bad ttl_seconds %q", args[3])
				return 2
			}
			ttl = n
		}
		scopes := splitScopes(args[2])
		for _, s := range scopes {
			if !consent.ValidScopeString(s) {
				errf("consent issue: %q is not a valid scope", s)
				return 2
			}
		}
		issuer, err := consent.NewIssuer(consent.IssuerOptions{SigningKey: key})
		if err != nil {
			errf("%v", err)
			return 1
		}
		scope, err := issuer.Issue(consent.IssueParams{
			Subject: args[1], Scopes: scopes, TTLSeconds: ttl,
		})
		if err != nil {
			errf("%v", err)
			return 1
		}
		fmt.Println(scope.Token)
		return 0

	case "verify":
		if len(args) < 2 {
			errf("consent verify: expected <token> [execution_id]")
			return 2
		}
		execID := ""
		if len(args) >= 3 {
			execID = args[2]
		}
		verifier, err := consent.NewVerifier(consent.VerifierOptions{VerificationKey: key})
		if err != nil {
			errf("%v", err)
			return 1
		}
		scope, err := verifier.Verify(args[1], execID)
		if err != nil {
			errf("%v", err)
			return 1
		}
		fmt.Printf("VALID\n  subject:      %s\n  scopes:       %s\n  jti:          %s\n"+
			"  execution_id: %s\n  expires_at:   %d\n",
			scope.Subject, strings.Join(scope.Scopes, ","), scope.JTI,
			orDash(scope.ExecutionID), scope.ExpiresAt)
		return 0

	default:
		errf("consent: unknown subcommand %q", args[0])
		return 2
	}
}

func orDash(s string) string {
	if s == "" {
		return "-"
	}
	return s
}

func splitScopes(s string) []string {
	if s == "" {
		return []string{}
	}
	parts := strings.Split(s, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		if p = strings.TrimSpace(p); p != "" {
			out = append(out, p)
		}
	}
	return out
}

func readJSONL(path string) ([]audit.Event, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer func() { _ = f.Close() }()

	var events []audit.Event
	sc := bufio.NewScanner(f)
	sc.Buffer(make([]byte, 0, 64*1024), 8*1024*1024)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" {
			continue
		}
		var ev audit.Event
		if err := json.Unmarshal([]byte(line), &ev); err != nil {
			continue // skip malformed lines rather than abort the report
		}
		events = append(events, ev)
	}
	return events, sc.Err()
}

func cmdAudit(args []string) int {
	if len(args) < 2 {
		errf("audit: expected 'tail', 'stats' or 'spend' and a file path")
		return 2
	}
	events, err := readJSONL(args[1])
	if err != nil {
		errf("%v", err)
		return 1
	}

	switch args[0] {
	case "tail":
		n := 20
		if len(args) >= 3 {
			if v, err := strconv.Atoi(args[2]); err == nil && v > 0 {
				n = v
			}
		}
		start := len(events) - n
		if start < 0 {
			start = 0
		}
		for _, ev := range events[start:] {
			b, _ := ev.JSON()
			fmt.Println(string(b))
		}
		return 0

	case "stats":
		byKind := map[string]int{}
		execs := map[string]struct{}{}
		for _, ev := range events {
			byKind[ev.Kind]++
			execs[ev.ExecutionID] = struct{}{}
		}
		fmt.Printf("events:     %d\n", len(events))
		fmt.Printf("executions: %d\n", len(execs))
		for _, k := range sortedKeys(byKind) {
			fmt.Printf("  %-24s %d\n", k, byKind[k])
		}
		return 0

	case "spend":
		groupBy := "tag"
		for i := 2; i < len(args)-1; i++ {
			if args[i] == "--group-by" {
				groupBy = args[i+1]
			}
		}
		if groupBy != "tag" && groupBy != "execution_id" {
			errf("audit spend: --group-by must be tag or execution_id")
			return 2
		}
		return reportSpend(events, groupBy)

	default:
		errf("audit: unknown subcommand %q", args[0])
		return 2
	}
}

// reportSpend aggregates spend_usd from engine.step events.
//
// spend_usd is cumulative per execution, so the per-execution total is the
// maximum observed, not the sum. Grouping by tag distributes each step's
// increment to the tag that caused it — that is the chargeback number.
func reportSpend(events []audit.Event, groupBy string) int {
	type acc struct {
		spend  float64
		tokens float64
		steps  int
	}
	groups := map[string]*acc{}
	lastByExec := map[string]float64{}
	sawSpend := false

	for _, ev := range events {
		if ev.Kind != "engine.step" {
			continue
		}
		spendAny, present := ev.Data["spend_usd"]
		if !present {
			continue
		}
		spend, ok := spendAny.(float64)
		if !ok {
			continue
		}
		sawSpend = true
		increment := spend - lastByExec[ev.ExecutionID]
		lastByExec[ev.ExecutionID] = spend

		key := ev.ExecutionID
		if groupBy == "tag" {
			key = "(untagged)"
			if t, ok := ev.Data["tag"].(string); ok && t != "" {
				key = t
			}
		}
		a := groups[key]
		if a == nil {
			a = &acc{}
			groups[key] = a
		}
		a.spend += increment
		a.steps++
		if tk, ok := ev.Data["tokens"].(float64); ok {
			a.tokens += tk
		}
	}

	if !sawSpend {
		fmt.Println("no spend_usd fields found; configure pressure.model_costs to record spend")
		return 0
	}

	keys := make([]string, 0, len(groups))
	for k := range groups {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool { return groups[keys[i]].spend > groups[keys[j]].spend })

	total := 0.0
	fmt.Printf("%-32s %12s %10s %8s\n", strings.ToUpper(groupBy), "SPEND_USD", "TOKENS", "STEPS")
	for _, k := range keys {
		a := groups[k]
		total += a.spend
		fmt.Printf("%-32s %12.6f %10.0f %8d\n", truncate(k, 32), a.spend, a.tokens, a.steps)
	}
	fmt.Printf("%-32s %12.6f\n", "TOTAL", total)
	return 0
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n-1] + "…"
}

func sortedKeys[V any](m map[string]V) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func cmdCoordinator(args []string) int {
	if len(args) == 0 || args[0] != "demo" {
		errf("coordinator: expected 'demo'")
		return 2
	}
	sink := audit.NewMemorySink()
	c, err := coordination.NewSharedPressureCoordinator(coordination.CoordinatorOptions{
		CoordinatorID:       "demo",
		EscalationThreshold: 1.0,
		ReleaseThreshold:    1.5,
		Sink:                sink,
		Callbacks: coordination.Callbacks{
			OnEscalation: func(s coordination.Snapshot) {
				fmt.Printf("ESCALATION aggregate=%.3f\n", s.Aggregate)
			},
			OnRelease: func(s coordination.Snapshot) {
				fmt.Printf("RELEASE    aggregate=%.3f\n", s.Aggregate)
			},
		},
	})
	if err != nil {
		errf("%v", err)
		return 1
	}
	_ = context.Background()
	for _, w := range []string{"worker-1", "worker-2", "worker-3"} {
		c.Register(w)
	}
	for i := 1; i <= 3; i++ {
		for _, w := range c.ExecutionIDs() {
			snap := c.Update(w, float64(i)*0.2)
			fmt.Printf("update %-8s p=%.2f aggregate=%.3f\n", w, float64(i)*0.2, snap.Aggregate)
		}
	}
	fmt.Printf("\nemitted %d coordinator events\n", sink.Len())
	return 0
}

func cmdConformance(args []string) int {
	specRoot := "./spec"
	if len(args) > 0 {
		specRoot = args[0]
	}
	results, err := conformance.RunAll(specRoot)
	if err != nil {
		errf("%v", err)
		return 1
	}
	for _, section := range conformance.Sections {
		vrs := results[section]
		passed := 0
		for _, r := range vrs {
			if r.Passed {
				passed++
			}
		}
		marker := "PASS"
		if passed < len(vrs) {
			marker = "FAIL"
			for _, r := range vrs {
				if !r.Passed {
					fmt.Printf("  [%s] %s: %s\n", section, r.Name, r.Message)
				}
			}
		}
		fmt.Printf("[%s] %s: %d/%d\n", marker, section, passed, len(vrs))
	}
	passed, total := results.CountPassed()
	fmt.Printf("\nconformance: %d/%d vectors passed\n", passed, total)
	if passed < total {
		return 1
	}
	return 0
}
