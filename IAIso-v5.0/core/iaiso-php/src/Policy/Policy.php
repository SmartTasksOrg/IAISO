<?php

declare(strict_types=1);

namespace IAIso\Policy;

use IAIso\Core\PressureConfig;

/** Assembled, validated policy document. */
final class Policy
{
    /** @param array<string,mixed> $metadata */
    public function __construct(
        public readonly string $version,
        public readonly PressureConfig $pressure,
        public readonly CoordinatorConfig $coordinator,
        public readonly ConsentPolicy $consent,
        public readonly Aggregator $aggregator,
        public readonly array $metadata = [],
    ) {
    }
}
