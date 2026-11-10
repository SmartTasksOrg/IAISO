<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Validated configuration for a {@see PressureEngine}. */
final class PressureConfig
{
    public function __construct(
        public readonly float $tokenCoefficient = 0.015,
        public readonly float $toolCoefficient = 0.08,
        public readonly float $depthCoefficient = 0.05,
        public readonly float $dissipationPerStep = 0.02,
        public readonly float $dissipationPerSecond = 0.0,
        public readonly float $escalationThreshold = 0.85,
        public readonly float $releaseThreshold = 0.95,
        public readonly bool $postReleaseLock = true,
    ) {
    }

    public static function defaults(): self
    {
        return new self();
    }

    public static function builder(): PressureConfigBuilder
    {
        return new PressureConfigBuilder();
    }

    /** Throws {@see ConfigException} if any field is out of range. */
    public function validate(): void
    {
        $nonNeg = [
            'token_coefficient'      => $this->tokenCoefficient,
            'tool_coefficient'       => $this->toolCoefficient,
            'depth_coefficient'      => $this->depthCoefficient,
            'dissipation_per_step'   => $this->dissipationPerStep,
            'dissipation_per_second' => $this->dissipationPerSecond,
        ];
        foreach ($nonNeg as $name => $val) {
            if ($val < 0) {
                throw new ConfigException("$name must be non-negative (got $val)");
            }
        }
        if ($this->escalationThreshold < 0.0 || $this->escalationThreshold > 1.0) {
            throw new ConfigException(
                "escalation_threshold must be in [0, 1] (got {$this->escalationThreshold})");
        }
        if ($this->releaseThreshold < 0.0 || $this->releaseThreshold > 1.0) {
            throw new ConfigException(
                "release_threshold must be in [0, 1] (got {$this->releaseThreshold})");
        }
        if ($this->releaseThreshold <= $this->escalationThreshold) {
            throw new ConfigException(
                "release_threshold must exceed escalation_threshold ({$this->releaseThreshold} <= {$this->escalationThreshold})");
        }
    }
}
