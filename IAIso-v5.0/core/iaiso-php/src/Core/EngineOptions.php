<?php

declare(strict_types=1);

namespace IAIso\Core;

use IAIso\Audit\Sink;

/** Options for {@see PressureEngine}. */
final class EngineOptions
{
    public function __construct(
        public readonly string $executionId,
        public readonly ?Sink $auditSink = null,
        public readonly ?Clock $clock = null,
        public readonly ?Clock $timestampClock = null,
    ) {
    }

    public static function builder(): EngineOptionsBuilder
    {
        return new EngineOptionsBuilder();
    }
}
