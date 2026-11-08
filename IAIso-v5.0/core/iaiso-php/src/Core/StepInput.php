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
        // A negative count would lower pressure. Refuse it.
        foreach (['tokens' => $tokens, 'toolCalls' => $toolCalls, 'depth' => $depth] as $name => $v) {
            if ($v < 0) {
                throw new \InvalidArgumentException("StepInput.{$name} must be >= 0, got {$v}");
            }
        }
    }

    /**
     * Build from untrusted decoded JSON (snake_case keys). Counts must be PHP
     * ints: floats, bools, numeric strings and null are refused instead of
     * being coerced, which `int` parameters do in non-strict callers.
     *
     * @param array<string, mixed> $a
     */
    public static function fromArray(array $a): self
    {
        $counts = ['tokens' => 0, 'tool_calls' => 0, 'depth' => 0];
        $tag = null;
        foreach ($a as $k => $v) {
            if (array_key_exists($k, $counts)) {
                if (!is_int($v) || $v < 0) {
                    throw new \InvalidArgumentException(
                        "StepInput.{$k} must be a non-negative integer, got " . json_encode($v)
                    );
                }
                $counts[$k] = $v;
            } elseif ($k === 'tag') {
                if ($v !== null && !is_string($v)) {
                    throw new \InvalidArgumentException('StepInput.tag must be a string or null');
                }
                $tag = $v;
            } else {
                throw new \InvalidArgumentException("StepInput: unknown field {$k}");
            }
        }
        return new self($counts['tokens'], $counts['tool_calls'], $counts['depth'], $tag);
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
