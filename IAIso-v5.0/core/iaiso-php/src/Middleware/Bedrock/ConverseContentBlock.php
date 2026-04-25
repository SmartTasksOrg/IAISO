<?php

declare(strict_types=1);

namespace IAIso\Middleware\Bedrock;

final class ConverseContentBlock
{
    public function __construct(public readonly bool $hasToolUse = false) {}
}
