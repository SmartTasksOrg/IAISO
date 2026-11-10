//! Pressure engine configuration.

use thiserror::Error;

/// Errors produced when building or validating a config.
#[derive(Debug, Error, PartialEq, Eq)]
pub enum ConfigError {
    #[error("escalation_threshold must be in [0, 1], got {0}")]
    EscalationThresholdOutOfRange(String),
    #[error("release_threshold must be in [0, 1], got {0}")]
    ReleaseThresholdOutOfRange(String),
    #[error("release_threshold must exceed escalation_threshold ({rel} <= {esc})")]
    ReleaseAtOrBelowEscalation { esc: String, rel: String },
    #[error("token_coefficient must be non-negative, got {0}")]
    NegativeTokenCoefficient(String),
    #[error("tool_coefficient must be non-negative, got {0}")]
    NegativeToolCoefficient(String),
    #[error("depth_coefficient must be non-negative, got {0}")]
    NegativeDepthCoefficient(String),
    #[error("dissipation_per_step must be non-negative, got {0}")]
    NegativeDissipationPerStep(String),
    #[error("dissipation_per_second must be non-negative, got {0}")]
    NegativeDissipationPerSecond(String),
}

/// Pressure engine configuration. See
/// `../../../spec/pressure/README.md §2` for normative ranges.
///
/// The recommended pattern is to start from [`PressureConfig::default`]
/// and override fields:
///
/// ```
/// # use iaiso_core::PressureConfig;
/// let cfg = PressureConfig {
///     escalation_threshold: 0.7,
///     post_release_lock: false,
///     ..PressureConfig::default()
/// };
/// ```
#[derive(Debug, Clone, Copy, PartialEq)]
pub struct PressureConfig {
    pub escalation_threshold: f64,
    pub release_threshold: f64,
    pub dissipation_per_step: f64,
    pub dissipation_per_second: f64,
    pub token_coefficient: f64,
    pub tool_coefficient: f64,
    pub depth_coefficient: f64,
    pub post_release_lock: bool,
}

impl Default for PressureConfig {
    fn default() -> Self {
        Self {
            escalation_threshold: 0.85,
            release_threshold: 0.95,
            dissipation_per_step: 0.02,
            dissipation_per_second: 0.0,
            token_coefficient: 0.015,
            tool_coefficient: 0.08,
            depth_coefficient: 0.05,
            post_release_lock: true,
        }
    }
}

impl PressureConfig {
    /// Validate the config for internal consistency.
    pub fn validate(&self) -> Result<(), ConfigError> {
        if !(0.0..=1.0).contains(&self.escalation_threshold) {
            return Err(ConfigError::EscalationThresholdOutOfRange(
                format!("{}", self.escalation_threshold),
            ));
        }
        if !(0.0..=1.0).contains(&self.release_threshold) {
            return Err(ConfigError::ReleaseThresholdOutOfRange(
                format!("{}", self.release_threshold),
            ));
        }
        if self.release_threshold <= self.escalation_threshold {
            return Err(ConfigError::ReleaseAtOrBelowEscalation {
                esc: format!("{}", self.escalation_threshold),
                rel: format!("{}", self.release_threshold),
            });
        }
        if self.token_coefficient < 0.0 {
            return Err(ConfigError::NegativeTokenCoefficient(format!(
                "{}",
                self.token_coefficient
            )));
        }
        if self.tool_coefficient < 0.0 {
            return Err(ConfigError::NegativeToolCoefficient(format!(
                "{}",
                self.tool_coefficient
            )));
        }
        if self.depth_coefficient < 0.0 {
            return Err(ConfigError::NegativeDepthCoefficient(format!(
                "{}",
                self.depth_coefficient
            )));
        }
        if self.dissipation_per_step < 0.0 {
            return Err(ConfigError::NegativeDissipationPerStep(format!(
                "{}",
                self.dissipation_per_step
            )));
        }
        if self.dissipation_per_second < 0.0 {
            return Err(ConfigError::NegativeDissipationPerSecond(format!(
                "{}",
                self.dissipation_per_second
            )));
        }
        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn default_validates() {
        assert!(PressureConfig::default().validate().is_ok());
    }

    #[test]
    fn rejects_release_below_escalation() {
        let cfg = PressureConfig {
            escalation_threshold: 0.9,
            release_threshold: 0.5,
            ..PressureConfig::default()
        };
        assert!(matches!(
            cfg.validate(),
            Err(ConfigError::ReleaseAtOrBelowEscalation { .. })
        ));
    }

    #[test]
    fn rejects_negative_coefficient() {
        let cfg = PressureConfig {
            token_coefficient: -0.01,
            ..PressureConfig::default()
        };
        assert!(matches!(
            cfg.validate(),
            Err(ConfigError::NegativeTokenCoefficient(_))
        ));
    }

    #[test]
    fn rejects_threshold_out_of_range() {
        let cfg = PressureConfig {
            escalation_threshold: 1.5,
            ..PressureConfig::default()
        };
        assert!(matches!(
            cfg.validate(),
            Err(ConfigError::EscalationThresholdOutOfRange(_))
        ));
    }
}
