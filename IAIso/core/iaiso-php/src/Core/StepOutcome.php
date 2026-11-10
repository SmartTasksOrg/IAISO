<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Outcome of a {@see PressureEngine::step()} call. Wire form is lowercase. */
enum StepOutcome: string
{
    case Ok         = 'ok';
    case Escalated  = 'escalated';
    case Released   = 'released';
    case Locked     = 'locked';
}
