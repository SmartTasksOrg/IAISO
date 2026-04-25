<?php

declare(strict_types=1);

namespace IAIso\Policy;

/** Coordinator-section configuration from a parsed policy. */
final class CoordinatorConfig
{
    public function __construct(
        public readonly float $escalationThreshold = 5.0,
        public readonly float $releaseThreshold = 8.0,
        public readonly float $notifyCooldownSeconds = 1.0,
    ) {
    }

    public static function defaults(): self
    {
        return new self();
    }
}
