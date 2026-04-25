<?php

declare(strict_types=1);

namespace IAIso\Audit;

/** Stores events in memory. Useful for tests. */
final class MemorySink implements Sink
{
    /** @var Event[] */
    private array $events = [];

    public function emit(Event $event): void
    {
        $this->events[] = $event;
    }

    /** @return Event[] */
    public function events(): array
    {
        return $this->events;
    }

    public function clear(): void
    {
        $this->events = [];
    }
}
