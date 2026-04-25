//! IAIso admin CLI.
//!
//! Subcommands: `policy`, `consent`, `audit`, `coordinator`, `conformance`.
//! See [`run`] for the entry point.

use iaiso_audit::{Event, MemorySink, NullSink, Sink};
use iaiso_consent::{
    Issuer, IssuerOptions, SignatureAlgorithm, Verifier, VerifierOptions,
};
use iaiso_coordination::{Callbacks, CoordinatorOptions, SharedPressureCoordinator, Snapshot};
use iaiso_policy::{load, Aggregator, SumAggregator};
use serde_json::{json, Value};
use std::fs;
use std::io::{BufRead, BufReader};
use std::path::Path;
use std::sync::Arc;

/// CLI entry point. Returns a process exit code.
pub fn run(args: &[String]) -> i32 {
    if args.is_empty() || args[0] == "-h" || args[0] == "--help" {
        print_help();
        return 0;
    }
    match args[0].as_str() {
        "policy" => cmd_policy(&args[1..]),
        "consent" => cmd_consent(&args[1..]),
        "audit" => cmd_audit(&args[1..]),
        "coordinator" => cmd_coordinator(&args[1..]),
        "conformance" => cmd_conformance(&args[1..]),
        other => {
            eprintln!("unknown command: {}", other);
            print_help();
            2
        }
    }
}

fn print_help() {
    println!(
        r#"IAIso admin CLI

Subcommands:
  policy validate <file>                 check a policy file for errors
  policy template <file>                 write a blank policy template
  consent issue <sub> <scope,...> [ttl]  issue a token (needs IAISO_HS256_SECRET)
  consent verify <token>                 verify a token
  audit tail <jsonl-file>                pretty-print JSONL audit events
  audit stats <jsonl-file>               summarize events by kind
  coordinator demo                       in-memory coordinator smoke test
  conformance <spec-dir>                 run the conformance suite"#
    );
}

fn cmd_policy(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: iaiso policy [validate|template] <file>");
        return 2;
    }
    match args[0].as_str() {
        "validate" => {
            if args.len() != 2 {
                eprintln!("usage: iaiso policy validate <file>");
                return 2;
            }
            match load(&args[1]) {
                Ok(p) => {
                    println!("OK: policy v{}", p.version);
                    println!(
                        "  pressure.escalation_threshold = {}",
                        p.pressure.escalation_threshold
                    );
                    println!(
                        "  coordinator.aggregator        = {}",
                        p.aggregator.name().as_str()
                    );
                    println!(
                        "  consent.issuer                = {}",
                        p.consent.issuer.unwrap_or_else(|| "(none)".to_string())
                    );
                    0
                }
                Err(e) => {
                    eprintln!("INVALID: {}", e);
                    1
                }
            }
        }
        "template" => {
            if args.len() != 2 {
                eprintln!("usage: iaiso policy template <file>");
                return 2;
            }
            let template = json!({
                "version": "1",
                "pressure": {
                    "escalation_threshold": 0.85,
                    "release_threshold": 0.95,
                    "token_coefficient": 0.015,
                    "tool_coefficient": 0.08,
                    "depth_coefficient": 0.05,
                    "dissipation_per_step": 0.02,
                    "dissipation_per_second": 0.0,
                    "post_release_lock": true
                },
                "coordinator": {
                    "aggregator": "sum",
                    "escalation_threshold": 5.0,
                    "release_threshold": 8.0,
                    "notify_cooldown_seconds": 1.0
                },
                "consent": {
                    "issuer": "iaiso",
                    "default_ttl_seconds": 3600,
                    "required_scopes": [],
                    "allowed_algorithms": ["HS256", "RS256"]
                },
                "metadata": {}
            });
            let body = serde_json::to_string_pretty(&template).unwrap();
            if let Err(e) = fs::write(&args[1], body + "\n") {
                eprintln!("write {}: {}", args[1], e);
                return 1;
            }
            println!("Wrote template to {}", args[1]);
            0
        }
        other => {
            eprintln!("unknown policy subcommand: {}", other);
            2
        }
    }
}

fn cmd_consent(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: iaiso consent [issue|verify] ...");
        return 2;
    }
    let secret = match std::env::var("IAISO_HS256_SECRET") {
        Ok(s) => s,
        Err(_) => {
            eprintln!("error: IAISO_HS256_SECRET must be set in the environment");
            return 2;
        }
    };
    match args[0].as_str() {
        "issue" => {
            if args.len() < 3 {
                eprintln!("usage: iaiso consent issue <subject> <scope1,scope2,...> [ttl_seconds]");
                return 2;
            }
            let ttl: i64 = args
                .get(3)
                .and_then(|s| s.parse().ok())
                .unwrap_or(3600);
            let scopes: Vec<String> = args[2]
                .split(',')
                .map(|s| s.trim().to_string())
                .filter(|s| !s.is_empty())
                .collect();
            let issuer = Issuer::new(IssuerOptions {
                signing_key: secret.as_bytes().to_vec(),
                algorithm: SignatureAlgorithm::HS256,
                issuer: "iaiso".to_string(),
                default_ttl_seconds: ttl,
                clock: None,
            });
            match issuer.issue(&args[1], scopes, None, Some(ttl), None) {
                Ok(scope) => {
                    let out = json!({
                        "token": scope.token,
                        "subject": scope.subject,
                        "scopes": scope.scopes,
                        "jti": scope.jti,
                        "expires_at": scope.expires_at,
                    });
                    println!("{}", serde_json::to_string_pretty(&out).unwrap());
                    0
                }
                Err(e) => {
                    eprintln!("issue failed: {}", e);
                    1
                }
            }
        }
        "verify" => {
            if args.len() != 2 {
                eprintln!("usage: iaiso consent verify <token>");
                return 2;
            }
            let verifier = Verifier::new(VerifierOptions {
                verification_key: secret.as_bytes().to_vec(),
                algorithm: SignatureAlgorithm::HS256,
                issuer: "iaiso".to_string(),
                revocation_list: None,
                leeway_seconds: 5,
                clock: None,
            });
            match verifier.verify(&args[1], None) {
                Ok(scope) => {
                    let out = json!({
                        "status": "valid",
                        "subject": scope.subject,
                        "scopes": scope.scopes,
                        "jti": scope.jti,
                        "expires_at": scope.expires_at,
                        "execution_id": scope.execution_id,
                    });
                    println!("{}", serde_json::to_string_pretty(&out).unwrap());
                    0
                }
                Err(e) => {
                    let msg = e.to_string().to_lowercase();
                    let status = if msg.contains("expir") {
                        "expired"
                    } else if msg.contains("revok") {
                        "revoked"
                    } else {
                        "invalid"
                    };
                    eprintln!("{}: {}", status, e);
                    1
                }
            }
        }
        other => {
            eprintln!("unknown consent subcommand: {}", other);
            2
        }
    }
}

fn cmd_audit(args: &[String]) -> i32 {
    if args.is_empty() {
        eprintln!("usage: iaiso audit [tail|stats] <jsonl-file>");
        return 2;
    }
    match args[0].as_str() {
        "tail" => {
            if args.len() != 2 {
                eprintln!("usage: iaiso audit tail <jsonl-file>");
                return 2;
            }
            tail_jsonl(Path::new(&args[1]))
        }
        "stats" => {
            if args.len() != 2 {
                eprintln!("usage: iaiso audit stats <jsonl-file>");
                return 2;
            }
            stats_jsonl(Path::new(&args[1]))
        }
        other => {
            eprintln!("unknown audit subcommand: {}", other);
            2
        }
    }
}

fn tail_jsonl(path: &Path) -> i32 {
    let f = match fs::File::open(path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("open {}: {}", path.display(), e);
            return 1;
        }
    };
    let reader = BufReader::new(f);
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        match serde_json::from_str::<Value>(line) {
            Ok(ev) => {
                let ts = ev
                    .get("timestamp")
                    .and_then(Value::as_f64)
                    .map(|t| format!("{:.3}", t))
                    .unwrap_or_else(|| "?".to_string());
                let kind = ev.get("kind").and_then(Value::as_str).unwrap_or("?");
                let exec = ev.get("execution_id").and_then(Value::as_str).unwrap_or("?");
                println!("{:<15}  {:<28}  {}", ts, kind, exec);
            }
            Err(_) => {
                let trunc = if line.len() > 80 { &line[..80] } else { line };
                println!("  [unparseable] {}", trunc);
            }
        }
    }
    0
}

fn stats_jsonl(path: &Path) -> i32 {
    let f = match fs::File::open(path) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("open {}: {}", path.display(), e);
            return 1;
        }
    };
    let reader = BufReader::new(f);
    let mut counts: std::collections::BTreeMap<String, usize> = std::collections::BTreeMap::new();
    let mut executions = std::collections::BTreeSet::new();
    let mut total = 0usize;
    for line in reader.lines() {
        let line = match line {
            Ok(l) => l,
            Err(_) => continue,
        };
        let line = line.trim();
        if line.is_empty() {
            continue;
        }
        if let Ok(ev) = serde_json::from_str::<Value>(line) {
            total += 1;
            if let Some(k) = ev.get("kind").and_then(Value::as_str) {
                *counts.entry(k.to_string()).or_insert(0) += 1;
            }
            if let Some(e) = ev.get("execution_id").and_then(Value::as_str) {
                executions.insert(e.to_string());
            }
        }
    }
    println!("total events: {}", total);
    println!("distinct executions: {}", executions.len());
    let mut pairs: Vec<(String, usize)> = counts.into_iter().collect();
    pairs.sort_by(|a, b| b.1.cmp(&a.1));
    for (k, v) in pairs {
        println!("  {:>6}  {}", v, k);
    }
    0
}

fn cmd_coordinator(args: &[String]) -> i32 {
    if args.is_empty() || args[0] != "demo" {
        eprintln!("usage: iaiso coordinator demo");
        return 2;
    }
    let sink: Arc<dyn Sink> = Arc::new(MemorySink::new());
    let c = match SharedPressureCoordinator::new(CoordinatorOptions {
        coordinator_id: "cli-demo".to_string(),
        escalation_threshold: 1.5,
        release_threshold: 2.5,
        notify_cooldown_seconds: 0.0,
        aggregator: Box::new(SumAggregator),
        audit_sink: sink,
        callbacks: Callbacks {
            on_escalation: Some(Arc::new(|s: Snapshot| {
                println!(
                    "  [callback] ESCALATION at aggregate={:.3}",
                    s.aggregate_pressure
                );
            })),
            on_release: Some(Arc::new(|s: Snapshot| {
                println!(
                    "  [callback] RELEASE at aggregate={:.3}",
                    s.aggregate_pressure
                );
            })),
        },
        clock: Arc::new(|| 0.0),
    }) {
        Ok(c) => c,
        Err(e) => {
            eprintln!("error: {}", e);
            return 1;
        }
    };
    let workers = ["worker-a", "worker-b", "worker-c"];
    for w in workers.iter() {
        c.register(*w);
    }
    println!("Demo: 3 workers registered. Stepping pressures...");
    let steps = [0.3_f64, 0.6, 0.9, 0.6];
    for (i, p) in steps.iter().enumerate() {
        for w in workers.iter() {
            if let Err(e) = c.update(w, *p) {
                eprintln!("error: {}", e);
                return 1;
            }
        }
        let snap = c.snapshot();
        println!(
            "  step {}: per-worker={:.2}  aggregate={:.3}  lifecycle={}",
            i + 1,
            p,
            snap.aggregate_pressure,
            snap.lifecycle.as_str()
        );
    }
    let _ = NullSink; // silence unused-import-style warning
    let _ = Event::new("", "", 0.0, std::collections::BTreeMap::new());
    0
}

fn cmd_conformance(args: &[String]) -> i32 {
    let spec_root = if args.is_empty() {
        Path::new("./spec")
    } else {
        Path::new(&args[0])
    };
    match iaiso_conformance::run_all(spec_root) {
        Ok(results) => {
            let mut fail = 0;
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
                    fail += total - pass;
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
            if fail > 0 {
                1
            } else {
                0
            }
        }
        Err(e) => {
            eprintln!("error: {}", e);
            1
        }
    }
}
