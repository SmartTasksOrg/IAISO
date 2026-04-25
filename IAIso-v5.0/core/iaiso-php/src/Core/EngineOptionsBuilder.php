<?php

declare(strict_types=1);

namespace IAIso\Core;

use IAIso\Audit\Sink;

final class EngineOptionsBuilder
{
    private string $executionId = '';
    private ?Sink $auditSink = null;
    private ?Clock $clock = null;
    private ?Clock $timestampClock = null;

    public function executionId(string $v): self    { $this->executionId = $v; return $this; }
    public function auditSink(?Sink $v): self       { $this->auditSink = $v; return $this; }
    public function clock(?Clock $v): self          { $this->clock = $v; return $this; }
    public function timestampClock(?Clock $v): self { $this->timestampClock = $v; return $this; }

    public function build(): EngineOptions
    {
        return new EngineOptions($this->executionId, $this->auditSink, $this->clock, $this->timestampClock);
    }
}
