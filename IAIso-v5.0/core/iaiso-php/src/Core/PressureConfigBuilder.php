<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Mutable builder for {@see PressureConfig}. */
final class PressureConfigBuilder
{
    private float $tokenCoefficient = 0.015;
    private float $toolCoefficient = 0.08;
    private float $depthCoefficient = 0.05;
    private float $dissipationPerStep = 0.02;
    private float $dissipationPerSecond = 0.0;
    private float $escalationThreshold = 0.85;
    private float $releaseThreshold = 0.95;
    private bool $postReleaseLock = true;

    public function tokenCoefficient(float $v): self        { $this->tokenCoefficient = $v; return $this; }
    public function toolCoefficient(float $v): self         { $this->toolCoefficient = $v; return $this; }
    public function depthCoefficient(float $v): self        { $this->depthCoefficient = $v; return $this; }
    public function dissipationPerStep(float $v): self      { $this->dissipationPerStep = $v; return $this; }
    public function dissipationPerSecond(float $v): self    { $this->dissipationPerSecond = $v; return $this; }
    public function escalationThreshold(float $v): self     { $this->escalationThreshold = $v; return $this; }
    public function releaseThreshold(float $v): self        { $this->releaseThreshold = $v; return $this; }
    public function postReleaseLock(bool $v): self          { $this->postReleaseLock = $v; return $this; }

    public function build(): PressureConfig
    {
        return new PressureConfig(
            $this->tokenCoefficient, $this->toolCoefficient, $this->depthCoefficient,
            $this->dissipationPerStep, $this->dissipationPerSecond,
            $this->escalationThreshold, $this->releaseThreshold, $this->postReleaseLock,
        );
    }
}
