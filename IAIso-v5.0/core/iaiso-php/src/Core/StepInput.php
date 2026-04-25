<?php

declare(strict_types=1);

namespace IAIso\Core;

/** A single step's worth of work. */
final class StepInput
{
    public function __construct(
        public readonly int $tokens = 0,
        public readonly int $toolCalls = 0,
        public readonly int $depth = 0,
        public readonly ?string $tag = null,
    ) {
    }

    public static function empty(): self
    {
        return new self();
    }

    public static function builder(): StepInputBuilder
    {
        return new StepInputBuilder();
    }
}
