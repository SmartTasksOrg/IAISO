<?php

declare(strict_types=1);

namespace IAIso\Conformance;

/** Result of running one vector. */
final class VectorResult
{
    public function __construct(
        public readonly string $section,
        public readonly string $name,
        public readonly bool $passed,
        public readonly string $message = '',
    ) {
    }

    public static function pass(string $section, string $name): self
    {
        return new self($section, $name, true);
    }

    public static function fail(string $section, string $name, string $message): self
    {
        return new self($section, $name, false, $message);
    }
}
