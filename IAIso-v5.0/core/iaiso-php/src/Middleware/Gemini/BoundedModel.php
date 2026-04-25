<?php

declare(strict_types=1);

namespace IAIso\Middleware\Gemini;

use IAIso\Core\BoundedExecution;
use IAIso\Core\StepInput;
use IAIso\Core\StepOutcome;
use IAIso\Middleware\EscalationRaisedException;
use IAIso\Middleware\LockedException;
use IAIso\Middleware\ProviderException;

/** IAIso wrapper for Google Gemini / Vertex AI generative models. */
final class BoundedModel
{
    private readonly Options $opts;

    public function __construct(
        private readonly Model $raw,
        private readonly BoundedExecution $execution,
        ?Options $opts = null,
    ) {
        $this->opts = $opts ?? Options::defaults();
    }

    /** @param array<string,mixed> $request */
    public function generateContent(array $request): Response
    {
        $pre = $this->execution->check();
        if ($pre === StepOutcome::Locked) throw new LockedException();
        if ($pre === StepOutcome::Escalated && $this->opts->raiseOnEscalation) {
            throw new EscalationRaisedException();
        }
        try {
            $resp = $this->raw->generateContent($request);
        } catch (\Throwable $e) {
            throw new ProviderException($e->getMessage(), $e);
        }
        $tokens = $resp->usageMetadata->totalTokenCount;
        if ($tokens === 0) {
            $tokens = $resp->usageMetadata->promptTokenCount + $resp->usageMetadata->candidatesTokenCount;
        }
        $toolCalls = 0;
        foreach ($resp->candidates as $c) {
            foreach ($c->parts as $p) {
                if ($p->hasFunctionCall) $toolCalls++;
            }
        }
        $model = $this->raw->modelName() !== '' ? $this->raw->modelName() : 'unknown';
        $this->execution->recordStep(new StepInput(
            tokens: $tokens, toolCalls: $toolCalls,
            tag: "gemini.generateContent:$model"));
        return $resp;
    }
}
