<?php

declare(strict_types=1);

namespace IAIso\Observability;

interface Span
{
    /** @param array<string,mixed> $attributes */
    public function addEvent(string $name, array $attributes): void;
    public function setAttribute(string $key, mixed $value): void;
    public function end(): void;
}
