//! Cross-execution pressure aggregation.
//!
//! [`SharedPressureCoordinator`] handles a single process;
//! [`RedisCoordinator`] is interoperable across processes and language
//! runtimes via the normative Lua script in
//! `../../spec/coordinator/README.md §1.2`.

use iaiso_audit::{Event, NullSink, Sink};
use iaiso_policy::{Aggregator, SumAggregator};
use parking_lot::Mutex;
use serde_json::json;
use std::collections::BTreeMap;
use std::sync::Arc;
use thiserror::Error;

/// The normative Lua script used by [`RedisCoordinator::update`].
/// Verbatim from `../../spec/coordinator/README.md §1.2`.
pub const UPDATE_AND_FETCH_SCRIPT: &str = r#"
local pressures_key = KEYS[1]
local exec_id       = ARGV[1]
local new_pressure  = ARGV[2]
local ttl_seconds   = tonumber(ARGV[3])

redis.call('HSET', pressures_key, exec_id, new_pressure)
if ttl_seconds > 0 then
  redis.call('EXPIRE', pressures_key, ttl_seconds)
end

return redis.call('HGETALL', pressures_key)
"#;

/// Coordinator lifecycle state.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum CoordinatorLifecycle {
    Nominal,
    Escalated,
    Released,
}

impl CoordinatorLifecycle {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Nominal => "nominal",
            Self::Escalated => "escalated",
            Self::Released => "released",
        }
    }
}

#[derive(Debug, Clone)]
pub struct Snapshot {
    pub coordinator_id: String,
    pub aggregate_pressure: f64,
    pub lifecycle: CoordinatorLifecycle,
    pub active_executions: usize,
    pub per_execution: BTreeMap<String, f64>,
}

#[derive(Debug, Error)]
pub enum CoordinatorError {
    #[error("pressure must be in [0, 1], got {0}")]
    PressureOutOfRange(f64),
    #[error("release_threshold must exceed escalation_threshold ({rel} <= {esc})")]
    InvalidThresholds { esc: f64, rel: f64 },
    #[error("redis error: {0}")]
    Redis(String),
}

/// Callbacks fired on lifecycle transitions.
#[derive(Default, Clone)]
pub struct Callbacks {
    pub on_escalation: Option<Arc<dyn Fn(Snapshot) + Send + Sync>>,
    pub on_release: Option<Arc<dyn Fn(Snapshot) + Send + Sync>>,
}

/// Configuration for [`SharedPressureCoordinator`].
pub struct CoordinatorOptions {
    pub coordinator_id: String,
    pub escalation_threshold: f64,
    pub release_threshold: f64,
    pub aggregator: Box<dyn Aggregator>,
    pub audit_sink: Arc<dyn Sink>,
    pub callbacks: Callbacks,
    pub notify_cooldown_seconds: f64,
    pub clock: Arc<dyn Fn() -> f64 + Send + Sync>,
}

impl CoordinatorOptions {
    pub fn defaults() -> Self {
        Self {
            coordinator_id: "default".to_string(),
            escalation_threshold: 5.0,
            release_threshold: 8.0,
            aggregator: Box::new(SumAggregator),
            audit_sink: Arc::new(NullSink),
            callbacks: Callbacks::default(),
            notify_cooldown_seconds: 1.0,
            clock: Arc::new(|| {
                use std::time::{SystemTime, UNIX_EPOCH};
                SystemTime::now()
                    .duration_since(UNIX_EPOCH)
                    .map(|d| d.as_secs_f64())
                    .unwrap_or(0.0)
            }),
        }
    }
}

struct SharedState {
    pressures: BTreeMap<String, f64>,
    lifecycle: CoordinatorLifecycle,
    last_notify_at: f64,
}

/// In-memory coordinator that aggregates pressure across a single
/// process's executions.
pub struct SharedPressureCoordinator {
    coordinator_id: String,
    escalation_threshold: f64,
    release_threshold: f64,
    notify_cooldown_seconds: f64,
    aggregator: Box<dyn Aggregator>,
    audit_sink: Arc<dyn Sink>,
    callbacks: Callbacks,
    clock: Arc<dyn Fn() -> f64 + Send + Sync>,
    state: Mutex<SharedState>,
}

impl SharedPressureCoordinator {
    pub fn new(opts: CoordinatorOptions) -> Result<Self, CoordinatorError> {
        if opts.release_threshold <= opts.escalation_threshold {
            return Err(CoordinatorError::InvalidThresholds {
                esc: opts.escalation_threshold,
                rel: opts.release_threshold,
            });
        }
        let agg_name = opts.aggregator.name();
        let coord = Self {
            coordinator_id: opts.coordinator_id,
            escalation_threshold: opts.escalation_threshold,
            release_threshold: opts.release_threshold,
            notify_cooldown_seconds: opts.notify_cooldown_seconds,
            aggregator: opts.aggregator,
            audit_sink: opts.audit_sink,
            callbacks: opts.callbacks,
            clock: opts.clock,
            state: Mutex::new(SharedState {
                pressures: BTreeMap::new(),
                lifecycle: CoordinatorLifecycle::Nominal,
                last_notify_at: 0.0,
            }),
        };
        coord.emit("coordinator.init", {
            let mut m = BTreeMap::new();
            m.insert("coordinator_id".to_string(), json!(coord.coordinator_id));
            m.insert("aggregator".to_string(), json!(agg_name.as_str()));
            m.insert("backend".to_string(), json!("memory"));
            m
        });
        Ok(coord)
    }

    pub fn coordinator_id(&self) -> &str {
        &self.coordinator_id
    }

    /// Register an execution with pressure 0.
    pub fn register(&self, execution_id: impl Into<String>) -> Snapshot {
        let id = execution_id.into();
        {
            let mut s = self.state.lock();
            s.pressures.insert(id.clone(), 0.0);
        }
        self.emit("coordinator.execution_registered", {
            let mut m = BTreeMap::new();
            m.insert("execution_id".to_string(), json!(id));
            m
        });
        self.snapshot()
    }

    pub fn unregister(&self, execution_id: &str) -> Snapshot {
        {
            let mut s = self.state.lock();
            s.pressures.remove(execution_id);
        }
        self.emit("coordinator.execution_unregistered", {
            let mut m = BTreeMap::new();
            m.insert("execution_id".to_string(), json!(execution_id));
            m
        });
        self.snapshot()
    }

    /// Update pressure for an execution and re-evaluate lifecycle.
    pub fn update(&self, execution_id: &str, pressure: f64) -> Result<Snapshot, CoordinatorError> {
        if !(0.0..=1.0).contains(&pressure) {
            return Err(CoordinatorError::PressureOutOfRange(pressure));
        }
        {
            let mut s = self.state.lock();
            s.pressures.insert(execution_id.to_string(), pressure);
        }
        Ok(self.evaluate())
    }

    pub fn reset(&self) -> usize {
        let count;
        {
            let mut s = self.state.lock();
            count = s.pressures.len();
            for v in s.pressures.values_mut() {
                *v = 0.0;
            }
            s.lifecycle = CoordinatorLifecycle::Nominal;
        }
        self.emit("coordinator.reset", {
            let mut m = BTreeMap::new();
            m.insert("fleet_size".to_string(), json!(count));
            m
        });
        count
    }

    pub fn snapshot(&self) -> Snapshot {
        let s = self.state.lock();
        let agg = self.aggregator.aggregate(&s.pressures);
        Snapshot {
            coordinator_id: self.coordinator_id.clone(),
            aggregate_pressure: agg,
            lifecycle: s.lifecycle,
            active_executions: s.pressures.len(),
            per_execution: s.pressures.clone(),
        }
    }

    fn evaluate(&self) -> Snapshot {
        let now = (self.clock)();
        let agg;
        let prior_lifecycle;
        let new_lifecycle;
        let in_cooldown;
        {
            let mut s = self.state.lock();
            agg = self.aggregator.aggregate(&s.pressures);
            prior_lifecycle = s.lifecycle;
            in_cooldown = (now - s.last_notify_at) < self.notify_cooldown_seconds;
            new_lifecycle = if agg >= self.release_threshold {
                CoordinatorLifecycle::Released
            } else if agg >= self.escalation_threshold {
                if prior_lifecycle == CoordinatorLifecycle::Nominal {
                    CoordinatorLifecycle::Escalated
                } else {
                    prior_lifecycle
                }
            } else {
                CoordinatorLifecycle::Nominal
            };
            s.lifecycle = new_lifecycle;
        }

        if new_lifecycle != prior_lifecycle && !in_cooldown {
            match new_lifecycle {
                CoordinatorLifecycle::Released => {
                    self.emit("coordinator.release", {
                        let mut m = BTreeMap::new();
                        m.insert("aggregate_pressure".to_string(), json!(agg));
                        m.insert("threshold".to_string(), json!(self.release_threshold));
                        m
                    });
                    {
                        let mut s = self.state.lock();
                        s.last_notify_at = now;
                    }
                    if let Some(cb) = &self.callbacks.on_release {
                        cb(self.snapshot());
                    }
                }
                CoordinatorLifecycle::Escalated => {
                    self.emit("coordinator.escalation", {
                        let mut m = BTreeMap::new();
                        m.insert("aggregate_pressure".to_string(), json!(agg));
                        m.insert("threshold".to_string(), json!(self.escalation_threshold));
                        m
                    });
                    {
                        let mut s = self.state.lock();
                        s.last_notify_at = now;
                    }
                    if let Some(cb) = &self.callbacks.on_escalation {
                        cb(self.snapshot());
                    }
                }
                CoordinatorLifecycle::Nominal => {
                    self.emit("coordinator.returned_to_nominal", {
                        let mut m = BTreeMap::new();
                        m.insert("aggregate_pressure".to_string(), json!(agg));
                        m
                    });
                    let mut s = self.state.lock();
                    s.last_notify_at = now;
                }
            }
        }
        self.snapshot()
    }

    fn emit(&self, kind: &str, data: BTreeMap<String, serde_json::Value>) {
        let event = Event::new(
            format!("coord:{}", self.coordinator_id),
            kind,
            (self.clock)(),
            data,
        );
        self.audit_sink.emit(&event);
    }
}

/// Structural Redis client interface. The official redis-rs Client and
/// any equivalent satisfy this with a thin adapter.
pub trait RedisClient: Send + Sync {
    /// Run a Lua script. KEYS and ARGV are passed positionally.
    fn eval(&self, script: &str, keys: &[&str], args: &[&str]) -> Result<RedisValue, String>;

    /// HSET key field value field value ...
    fn hset(&self, key: &str, fields: &[(&str, &str)]) -> Result<(), String>;

    /// HKEYS key
    fn hkeys(&self, key: &str) -> Result<Vec<String>, String>;
}

/// Redis return value, simplified.
#[derive(Debug, Clone)]
pub enum RedisValue {
    Nil,
    Int(i64),
    Bulk(String),
    Array(Vec<RedisValue>),
}

/// Parse a flat HGETALL result (the Lua script returns this) into a map.
pub fn parse_hgetall_flat(value: &RedisValue) -> BTreeMap<String, f64> {
    let mut out = BTreeMap::new();
    if let RedisValue::Array(items) = value {
        let mut iter = items.iter();
        while let (Some(k), Some(v)) = (iter.next(), iter.next()) {
            let k_s = match k {
                RedisValue::Bulk(s) => s.clone(),
                _ => continue,
            };
            let v_s = match v {
                RedisValue::Bulk(s) => s.clone(),
                _ => continue,
            };
            if let Ok(f) = v_s.parse::<f64>() {
                out.insert(k_s, f);
            }
        }
    }
    out
}

/// Redis-backed coordinator. Interoperable with the Python, Node, and
/// Go references via the shared keyspace and Lua script.
pub struct RedisCoordinator {
    redis: Arc<dyn RedisClient>,
    key_prefix: String,
    pressures_ttl_seconds: f64,
    shadow: SharedPressureCoordinator,
}

pub struct RedisCoordinatorOptions {
    pub redis: Arc<dyn RedisClient>,
    pub coordinator_id: String,
    pub escalation_threshold: f64,
    pub release_threshold: f64,
    pub key_prefix: String,
    pub pressures_ttl_seconds: f64,
    pub aggregator: Box<dyn Aggregator>,
    pub audit_sink: Arc<dyn Sink>,
    pub callbacks: Callbacks,
    pub notify_cooldown_seconds: f64,
    pub clock: Arc<dyn Fn() -> f64 + Send + Sync>,
}

impl RedisCoordinator {
    pub fn new(opts: RedisCoordinatorOptions) -> Result<Self, CoordinatorError> {
        let agg_name = opts.aggregator.name();
        let shadow = SharedPressureCoordinator::new(CoordinatorOptions {
            coordinator_id: opts.coordinator_id.clone(),
            escalation_threshold: opts.escalation_threshold,
            release_threshold: opts.release_threshold,
            aggregator: opts.aggregator,
            audit_sink: Arc::new(NullSink),
            callbacks: opts.callbacks,
            notify_cooldown_seconds: opts.notify_cooldown_seconds,
            clock: opts.clock.clone(),
        })?;
        // Emit init with the real backend label and the user's audit sink.
        let event = Event::new(
            format!("coord:{}", opts.coordinator_id),
            "coordinator.init",
            (opts.clock)(),
            {
                let mut m = BTreeMap::new();
                m.insert("coordinator_id".to_string(), json!(opts.coordinator_id));
                m.insert("aggregator".to_string(), json!(agg_name.as_str()));
                m.insert("backend".to_string(), json!("redis"));
                m
            },
        );
        opts.audit_sink.emit(&event);
        Ok(Self {
            redis: opts.redis,
            key_prefix: opts.key_prefix,
            pressures_ttl_seconds: opts.pressures_ttl_seconds,
            shadow,
        })
    }

    fn pressures_key(&self) -> String {
        format!("{}:{}:pressures", self.key_prefix, self.shadow.coordinator_id())
    }

    pub fn register(&self, execution_id: &str) -> Result<Snapshot, CoordinatorError> {
        self.redis
            .hset(&self.pressures_key(), &[(execution_id, "0.0")])
            .map_err(CoordinatorError::Redis)?;
        Ok(self.shadow.register(execution_id))
    }

    pub fn unregister(&self, execution_id: &str) -> Result<Snapshot, CoordinatorError> {
        let script = "redis.call('HDEL', KEYS[1], ARGV[1]); return 1";
        let key = self.pressures_key();
        self.redis
            .eval(script, &[&key], &[execution_id])
            .map_err(CoordinatorError::Redis)?;
        Ok(self.shadow.unregister(execution_id))
    }

    pub fn update(
        &self,
        execution_id: &str,
        pressure: f64,
    ) -> Result<Snapshot, CoordinatorError> {
        if !(0.0..=1.0).contains(&pressure) {
            return Err(CoordinatorError::PressureOutOfRange(pressure));
        }
        let key = self.pressures_key();
        let pressure_s = format!("{}", pressure);
        let ttl_s = format!("{}", self.pressures_ttl_seconds as i64);
        let result = self
            .redis
            .eval(
                UPDATE_AND_FETCH_SCRIPT,
                &[&key],
                &[execution_id, &pressure_s, &ttl_s],
            )
            .map_err(CoordinatorError::Redis)?;
        let parsed = parse_hgetall_flat(&result);
        // Replace shadow state from Redis truth
        {
            let mut s = self.shadow.state.lock();
            s.pressures = parsed;
        }
        Ok(self.shadow.evaluate())
    }

    pub fn reset(&self) -> Result<usize, CoordinatorError> {
        let key = self.pressures_key();
        let keys = self.redis.hkeys(&key).map_err(CoordinatorError::Redis)?;
        if !keys.is_empty() {
            let pairs: Vec<(&str, &str)> = keys.iter().map(|k| (k.as_str(), "0.0")).collect();
            self.redis
                .hset(&key, &pairs)
                .map_err(CoordinatorError::Redis)?;
        }
        Ok(self.shadow.reset())
    }

    pub fn snapshot(&self) -> Snapshot {
        self.shadow.snapshot()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use iaiso_audit::MemorySink;
    use std::sync::atomic::{AtomicUsize, Ordering};

    fn fixed_clock(t: f64) -> Arc<dyn Fn() -> f64 + Send + Sync> {
        Arc::new(move || t)
    }

    #[test]
    fn aggregates_sum() {
        let c = SharedPressureCoordinator::new(CoordinatorOptions {
            audit_sink: Arc::new(NullSink),
            ..CoordinatorOptions::defaults()
        })
        .unwrap();
        c.register("a");
        c.register("b");
        c.update("a", 0.3).unwrap();
        let snap = c.update("b", 0.5).unwrap();
        assert!((snap.aggregate_pressure - 0.8).abs() < 1e-9);
    }

    #[test]
    fn escalation_callback_fires() {
        let counter = Arc::new(AtomicUsize::new(0));
        let cb_counter = counter.clone();
        let c = SharedPressureCoordinator::new(CoordinatorOptions {
            escalation_threshold: 0.7,
            release_threshold: 0.95,
            notify_cooldown_seconds: 0.0,
            callbacks: Callbacks {
                on_escalation: Some(Arc::new(move |_| {
                    cb_counter.fetch_add(1, Ordering::SeqCst);
                })),
                on_release: None,
            },
            ..CoordinatorOptions::defaults()
        })
        .unwrap();
        c.register("a");
        c.update("a", 0.8).unwrap();
        assert_eq!(counter.load(Ordering::SeqCst), 1);
    }

    #[test]
    fn rejects_bad_pressure() {
        let c = SharedPressureCoordinator::new(CoordinatorOptions::defaults()).unwrap();
        assert!(c.update("a", 1.5).is_err());
        assert!(c.update("a", -0.1).is_err());
    }

    #[test]
    fn lua_script_unchanged_from_spec() {
        assert!(UPDATE_AND_FETCH_SCRIPT.contains("pressures_key = KEYS[1]"));
        assert!(UPDATE_AND_FETCH_SCRIPT.contains("HGETALL"));
        assert!(UPDATE_AND_FETCH_SCRIPT.contains("EXPIRE"));
    }

    /// Mock Redis for tests.
    struct MockRedis {
        hashes: Mutex<BTreeMap<String, BTreeMap<String, String>>>,
    }

    impl MockRedis {
        fn new() -> Self {
            Self {
                hashes: Mutex::new(BTreeMap::new()),
            }
        }
    }

    impl RedisClient for MockRedis {
        fn eval(
            &self,
            script: &str,
            keys: &[&str],
            args: &[&str],
        ) -> Result<RedisValue, String> {
            let mut hashes = self.hashes.lock();
            let key = keys[0].to_string();
            let h = hashes.entry(key).or_insert_with(BTreeMap::new);
            if script.contains("HSET") && script.contains("HGETALL") {
                h.insert(args[0].to_string(), args[1].to_string());
                let mut flat = Vec::new();
                for (k, v) in h.iter() {
                    flat.push(RedisValue::Bulk(k.clone()));
                    flat.push(RedisValue::Bulk(v.clone()));
                }
                Ok(RedisValue::Array(flat))
            } else if script.contains("HDEL") {
                h.remove(args[0]);
                Ok(RedisValue::Int(1))
            } else {
                Ok(RedisValue::Nil)
            }
        }

        fn hset(&self, key: &str, fields: &[(&str, &str)]) -> Result<(), String> {
            let mut hashes = self.hashes.lock();
            let h = hashes.entry(key.to_string()).or_insert_with(BTreeMap::new);
            for (k, v) in fields {
                h.insert(k.to_string(), v.to_string());
            }
            Ok(())
        }

        fn hkeys(&self, key: &str) -> Result<Vec<String>, String> {
            Ok(self
                .hashes
                .lock()
                .get(key)
                .map(|h| h.keys().cloned().collect())
                .unwrap_or_default())
        }
    }

    #[test]
    fn redis_coordinator_with_mock() {
        let mock: Arc<dyn RedisClient> = Arc::new(MockRedis::new());
        let c = RedisCoordinator::new(RedisCoordinatorOptions {
            redis: mock,
            coordinator_id: "test".to_string(),
            escalation_threshold: 0.7,
            release_threshold: 0.9,
            key_prefix: "iaiso:coord".to_string(),
            pressures_ttl_seconds: 300.0,
            aggregator: Box::new(SumAggregator),
            audit_sink: Arc::new(MemorySink::new()),
            callbacks: Callbacks::default(),
            notify_cooldown_seconds: 1.0,
            clock: fixed_clock(0.0),
        })
        .unwrap();
        c.register("a").unwrap();
        c.register("b").unwrap();
        c.update("a", 0.4).unwrap();
        let snap = c.update("b", 0.3).unwrap();
        assert!((snap.aggregate_pressure - 0.7).abs() < 1e-9);
    }

    #[test]
    fn parse_hgetall_flat_works() {
        let v = RedisValue::Array(vec![
            RedisValue::Bulk("a".to_string()),
            RedisValue::Bulk("0.3".to_string()),
            RedisValue::Bulk("b".to_string()),
            RedisValue::Bulk("0.5".to_string()),
        ]);
        let m = parse_hgetall_flat(&v);
        assert_eq!(m.get("a"), Some(&0.3));
        assert_eq!(m.get("b"), Some(&0.5));
    }
}
