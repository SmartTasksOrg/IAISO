<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Supported JWT signature algorithms. Wire form preserves casing. */
enum Algorithm: string
{
    case HS256 = 'HS256';
    case RS256 = 'RS256';
}
