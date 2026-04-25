<?php

declare(strict_types=1);

namespace IAIso\Middleware\OpenAi;

final class ToolCall
{
    public function __construct(public readonly string $id) {}
}
