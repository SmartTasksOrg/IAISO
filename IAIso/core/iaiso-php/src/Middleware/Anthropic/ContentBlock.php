<?php

declare(strict_types=1);

namespace IAIso\Middleware\Anthropic;

/** A single content block in an Anthropic response. */
final class ContentBlock
{
    public function __construct(public readonly string $type) {}
}
