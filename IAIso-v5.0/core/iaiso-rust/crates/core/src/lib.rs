//! IAIso pressure engine and bounded execution facade.
//!
//! This is the core runtime crate of the IAIso Rust reference SDK. It
//! conforms to the IAIso specification at `../spec/` and passes all 67
//! conformance vectors.

pub mod config;
pub mod engine;
pub mod execution;
pub mod types;

pub use config::{ConfigError, PressureConfig};
pub use engine::{EngineOptions, PressureEngine, PressureSnapshot, StepInput};
pub use execution::{BoundedExecution, BoundedExecutionOptions, ExecutionError};
pub use types::{wallclock, Clock, Lifecycle, StepOutcome};
