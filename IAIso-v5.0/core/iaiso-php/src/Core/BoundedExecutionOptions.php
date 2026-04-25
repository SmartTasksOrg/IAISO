<?php

declare(strict_types=1);

namespace IAIso\Core;

use IAIso\Audit\Sink;

/** Options for {@see BoundedExecution::start()}. */
final class BoundedExecutionOptions
{
    public function __construct(
        public readonly ?string $executionId = null,
        public readonly ?PressureConfig $config = null,
        public readonly ?Sink $auditSink = null,
        public readonly ?Clock $clock = null,
        public readonly ?Clock $timestampClock = null,
    ) {
    }
}
