//! iaiso-conformance — runs the full IAIso conformance suite against
//! this Rust implementation.
//!
//! Usage: `iaiso-conformance ./spec`

use std::path::PathBuf;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = std::env::args().collect();
    let spec_root = if args.len() >= 2 {
        PathBuf::from(&args[1])
    } else {
        PathBuf::from("./spec")
    };

    let results = match iaiso_conformance::run_all(&spec_root) {
        Ok(r) => r,
        Err(e) => {
            eprintln!("error: {}", e);
            return ExitCode::from(1);
        }
    };

    let mut total_fail = 0;
    for (name, vrs) in [
        ("pressure", &results.pressure),
        ("consent", &results.consent),
        ("events", &results.events),
        ("policy", &results.policy),
    ] {
        let pass = vrs.iter().filter(|v| v.passed).count();
        let total = vrs.len();
        let marker = if pass == total { "PASS" } else { "FAIL" };
        if pass != total {
            total_fail += total - pass;
            for v in vrs {
                if !v.passed {
                    println!("  [{}] {}: {}", name, v.name, v.message);
                }
            }
        }
        println!("[{}] {}: {}/{}", marker, name, pass, total);
    }

    let (pass, total) = results.count_passed();
    println!("\nconformance: {}/{} vectors passed", pass, total);
    if total_fail > 0 {
        ExitCode::from(1)
    } else {
        ExitCode::SUCCESS
    }
}
