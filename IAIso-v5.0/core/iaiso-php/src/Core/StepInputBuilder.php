<?php

declare(strict_types=1);

namespace IAIso\Core;

/** Mutable builder for {@see StepInput}. */
final class StepInputBuilder
{
    private int $tokens = 0;
    private int $toolCalls = 0;
    private int $depth = 0;
    private ?string $tag = null;

    public function tokens(int $v): self    { $this->tokens = $v; return $this; }
    public function toolCalls(int $v): self { $this->toolCalls = $v; return $this; }
    public function depth(int $v): self     { $this->depth = $v; return $this; }
    public function tag(?string $v): self   { $this->tag = $v; return $this; }

    public function build(): StepInput
    {
        return new StepInput($this->tokens, $this->toolCalls, $this->depth, $this->tag);
    }
}
