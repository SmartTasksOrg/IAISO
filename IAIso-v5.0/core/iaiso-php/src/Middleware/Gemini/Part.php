<?php

declare(strict_types=1);

namespace IAIso\Middleware\Gemini;

final class Part
{
    public function __construct(public readonly bool $hasFunctionCall = false) {}
}
