<?php

declare(strict_types=1);

namespace IAIso\Middleware\Anthropic;

/** Options for {@see BoundedClient}. */
final class Options
{
    public function __construct(public readonly bool $raiseOnEscalation = false) {}

    public static function defaults(): self
    {
        return new self();
    }
}
