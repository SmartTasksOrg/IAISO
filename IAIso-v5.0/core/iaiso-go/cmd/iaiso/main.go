// Command iaiso is the IAIso admin CLI. Subcommands cover policy
// validation, consent token issuance and verification, audit log
// inspection, in-memory coordinator demos, and the conformance suite.
//
// Usage:
//
//	iaiso --help
package main

import (
	"os"

	"github.com/iaiso/iaiso-go/iaiso/cli"
)

func main() {
	os.Exit(cli.Main(os.Args[1:]))
}
