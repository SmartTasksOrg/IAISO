<?php

declare(strict_types=1);

namespace IAIso\Audit;

/** Appends events as JSONL to a file. I/O errors are silently dropped. */
final class JsonlFileSink implements Sink
{
    public function __construct(private readonly string $path)
    {
    }

    public function emit(Event $event): void
    {
        $line = $event->toJson() . PHP_EOL;
        // LOCK_EX to keep multi-process writers from interleaving lines.
        @file_put_contents($this->path, $line, FILE_APPEND | LOCK_EX);
    }
}
