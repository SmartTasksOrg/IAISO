<?php

declare(strict_types=1);

namespace IAIso\Middleware\OpenAi;

final class Options
{
    public function __construct(public readonly bool $raiseOnEscalation = false) {}
    public static function defaults(): self { return new self(); }
}
