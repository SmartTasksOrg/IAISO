<?php

declare(strict_types=1);

namespace IAIso\Middleware\Cohere;

final class Meta
{
    public function __construct(
        public readonly ?BilledUnits $tokens = null,
        public readonly ?BilledUnits $billedUnits = null,
    ) {}
}
