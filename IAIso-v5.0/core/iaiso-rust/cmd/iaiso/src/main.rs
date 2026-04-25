//! Command `iaiso` — the IAIso admin CLI.
//!
//! Run `iaiso --help` for subcommands.

use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let code = iaiso_cli::run(&args);
    ExitCode::from(code as u8)
}
