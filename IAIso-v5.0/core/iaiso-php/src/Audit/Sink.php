<?php

declare(strict_types=1);

namespace IAIso\Audit;

/** A consumer of audit events. */
interface Sink
{
    public function emit(Event $event): void;
}
