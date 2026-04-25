// Command iaiso-conformance runs the full IAIso conformance suite
// against this implementation. Pass the path to the spec/ directory
// containing vectors.json files.
//
// Usage:
//
//	iaiso-conformance ./spec
package main

import (
	"fmt"
	"os"

	"github.com/iaiso/iaiso-go/iaiso/conformance"
)

func main() {
	specRoot := "./spec"
	if len(os.Args) > 1 {
		specRoot = os.Args[1]
	}
	results, err := conformance.RunAll(specRoot)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	fail := 0
	for _, section := range []string{"pressure", "consent", "events", "policy"} {
		vrs := results[section]
		pass := 0
		for _, r := range vrs {
			if r.Passed {
				pass++
			}
		}
		marker := "PASS"
		if pass < len(vrs) {
			marker = "FAIL"
			fail += len(vrs) - pass
			for _, r := range vrs {
				if !r.Passed {
					fmt.Printf("  [%s] %s: %s\n", section, r.Name, r.Message)
				}
			}
		}
		fmt.Printf("[%s] %s: %d/%d\n", marker, section, pass, len(vrs))
	}
	pass, total := results.CountPassed()
	fmt.Printf("\nconformance: %d/%d vectors passed\n", pass, total)
	if fail > 0 {
		os.Exit(1)
	}
}
