<?php

declare(strict_types=1);

namespace IAIso\Middleware\Gemini;

final class Response
{
    /** @param Candidate[] $candidates */
    public function __construct(
        public readonly UsageMetadata $usageMetadata,
        public readonly array $candidates,
    ) {
    }
}
