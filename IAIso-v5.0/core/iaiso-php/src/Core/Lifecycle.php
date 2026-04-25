<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Lifecycle states for a {@see PressureEngine}. Wire form is lowercase. */
enum Lifecycle: string
{
    case Init       = 'init';
    case Running    = 'running';
    case Escalated  = 'escalated';
    case Released   = 'released';
    case Locked     = 'locked';
}
