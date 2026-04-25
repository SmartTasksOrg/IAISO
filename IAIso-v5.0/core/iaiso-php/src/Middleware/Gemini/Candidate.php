<?php

declare(strict_types=1);

namespace IAIso\Middleware\Gemini;

final class Candidate
{
    /** @param Part[] $parts */
    public function __construct(public readonly array $parts = []) {}
}
