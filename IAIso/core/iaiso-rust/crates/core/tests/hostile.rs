//! spec/pressure/hostile.json is shared by every IAIso port.
use iaiso_audit::MemorySink;
use iaiso_core::{EngineOptions, PressureConfig, PressureEngine, StepInput};
use std::sync::Arc;

fn hostile() -> serde_json::Value {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/../../spec/pressure/hostile.json");
    serde_json::from_str(&std::fs::read_to_string(path).expect("read hostile.json")).unwrap()
}

fn engine() -> PressureEngine {
    let clk: iaiso_core::Clock = Arc::new(|| 0.0);
    PressureEngine::new(
        PressureConfig::default(),
        EngineOptions {
            execution_id: "hostile".into(),
            audit_sink: Arc::new(MemorySink::new()),
            clock: clk.clone(),
            timestamp_clock: clk,
        },
    )
    .unwrap()
}

#[test]
fn hostile_values_are_refused() {
    let h = hostile();
    let rejects = h["reject"].as_array().unwrap();
    assert!(rejects.len() >= 18);
    for v in rejects {
        let mut step = serde_json::Map::new();
        step.insert(v["field"].as_str().unwrap().into(), v["value"].clone());
        assert!(
            StepInput::from_json(&serde_json::Value::Object(step)).is_err(),
            "{} accepted",
            v["name"]
        );
    }
}

#[test]
fn extreme_values_are_handled() {
    for v in hostile()["accept"].as_array().unwrap() {
        let e = engine();
        let out = e.step(StepInput::from_json(&v["step"]).unwrap());
        let exp = &v["expect"];
        assert!(!e.pressure().is_nan());
        assert!((e.pressure() - exp["pressure"].as_f64().unwrap()).abs() < 1e-9, "{}", v["name"]);
        assert_eq!(out.as_str(), exp["outcome"].as_str().unwrap(), "{}", v["name"]);
        assert_eq!(e.lifecycle().as_str(), exp["lifecycle"].as_str().unwrap(), "{}", v["name"]);
    }
}

#[test]
fn unknown_fields_refused() {
    assert!(StepInput::from_json(&serde_json::json!({"token": 5})).is_err());
}
