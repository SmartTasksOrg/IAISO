<?php

declare(strict_types=1);

namespace IAIso\Coordination;

/** Lifecycle state of a fleet-aggregated coordinator. */
enum CoordinatorLifecycle: string
{
    case Nominal    = 'nominal';
    case Escalated  = 'escalated';
    case Released   = 'released';
}
