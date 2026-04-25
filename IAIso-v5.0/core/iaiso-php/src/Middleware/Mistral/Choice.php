<?php

declare(strict_types=1);

namespace IAIso\Middleware\Mistral;

final class Choice
{
    /** @param string[] $toolCalls */
    public function __construct(public readonly array $toolCalls = []) {}
}
