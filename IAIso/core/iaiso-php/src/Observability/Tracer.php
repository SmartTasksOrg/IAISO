<?php

declare(strict_types=1);

namespace IAIso\Observability;

interface Tracer
{
    /** @param array<string,mixed> $attributes */
    public function startSpan(string $name, array $attributes): Span;
}
