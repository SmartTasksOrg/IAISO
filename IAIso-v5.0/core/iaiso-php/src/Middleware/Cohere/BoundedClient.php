<?php

declare(strict_types=1);

namespace IAIso\Middleware\Cohere;

use IAIso\Core\BoundedExecution;
use IAIso\Core\StepInput;
use IAIso\Core\StepOutcome;
use IAIso\Middleware\EscalationRaisedException;
use IAIso\Middleware\LockedException;
use IAIso\Middleware\ProviderException;

/** IAIso wrapper for Cohere chat. */
final class BoundedClient
{
    private readonly Options $opts;

    public function __construct(
        private readonly Client $raw,
        private readonly BoundedExecution $execution,
        ?Options $opts = null,
    ) {
        $this->opts = $opts ?? Options::defaults();
    }

    /** @param array<string,mixed> $params */
    public function chat(array $params): Response
    {
        $pre = $this->execution->check();
        if ($pre === StepOutcome::Locked) throw new LockedException();
        if ($pre === StepOutcome::Escalated && $this->opts->raiseOnEscalation) {
            throw new EscalationRaisedException();
        }
        try {
            $resp = $this->raw->chat($params);
        } catch (\Throwable $e) {
            throw new ProviderException($e->getMessage(), $e);
        }
        $b = $resp->meta->tokens ?? $resp->meta->billedUnits;
        $tokens = $b !== null ? $b->inputTokens + $b->outputTokens : 0;
        $toolCalls = count($resp->toolCalls);
        $model = $resp->model !== '' ? $resp->model : 'unknown';
        $this->execution->recordStep(new StepInput(
            tokens: $tokens, toolCalls: $toolCalls,
            tag: "cohere.chat:$model"));
        return $resp;
    }
}
