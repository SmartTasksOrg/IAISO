<?php

declare(strict_types=1);

namespace IAIso\Middleware\Mistral;

use IAIso\Core\BoundedExecution;
use IAIso\Core\StepInput;
use IAIso\Core\StepOutcome;
use IAIso\Middleware\EscalationRaisedException;
use IAIso\Middleware\LockedException;
use IAIso\Middleware\ProviderException;

/** IAIso wrapper for Mistral chat. */
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
    public function chatComplete(array $params): Response
    {
        $pre = $this->execution->check();
        if ($pre === StepOutcome::Locked) throw new LockedException();
        if ($pre === StepOutcome::Escalated && $this->opts->raiseOnEscalation) {
            throw new EscalationRaisedException();
        }
        try {
            $resp = $this->raw->chatComplete($params);
        } catch (\Throwable $e) {
            throw new ProviderException($e->getMessage(), $e);
        }
        $tokens = $resp->usage->totalTokens;
        if ($tokens === 0) $tokens = $resp->usage->promptTokens + $resp->usage->completionTokens;
        $toolCalls = 0;
        foreach ($resp->choices as $c) $toolCalls += count($c->toolCalls);
        $model = $resp->model !== '' ? $resp->model : 'unknown';
        $this->execution->recordStep(new StepInput(
            tokens: $tokens, toolCalls: $toolCalls,
            tag: "mistral.chat.complete:$model"));
        return $resp;
    }
}
