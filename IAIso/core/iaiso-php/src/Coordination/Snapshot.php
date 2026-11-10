<?php

declare(strict_types=1);

namespace IAIso\Coordination;

/** Read-only view of coordinator state. */
final class Snapshot
{
    /** @param array<string,float> $perExecution */
    public function __construct(
        public readonly string $coordinatorId,
        public readonly float $aggregatePressure,
        public readonly CoordinatorLifecycle $lifecycle,
        public readonly int $activeExecutions,
        public readonly array $perExecution,
    ) {
    }
}
