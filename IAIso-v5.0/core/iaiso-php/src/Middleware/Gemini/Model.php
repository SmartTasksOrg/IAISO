<?php

declare(strict_types=1);

namespace IAIso\Middleware\Gemini;

interface Model
{
    /** @param array<string,mixed> $request */
    public function generateContent(array $request): Response;
    public function modelName(): string;
}
