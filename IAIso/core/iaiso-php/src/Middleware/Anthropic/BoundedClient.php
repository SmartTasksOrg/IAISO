<?php

declare(strict_types=1);

namespace IAIso\Middleware\Anthropic;

use IAIso\Core\BoundedExecution;
use IAIso\Core\StepInput;
use IAIso\Core\StepOutcome;
use IAIso\Middleware\EscalationRaisedException;
use IAIso\Middleware\LockedException;
use IAIso\Middleware\ProviderException;

/** Wraps a {@see Client} so every call is accounted against a {@see BoundedExecution}. */
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
    public function messagesCreate(array $params): Response
    {
        $pre = $this->execution->check();
        if ($pre === StepOutcome::Locked) throw new LockedException();
        if ($pre === StepOutcome::Escalated && $this->opts->raiseOnEscalation) {
            throw new EscalationRaisedException();
        }
        try {
            $resp = $this->raw->messagesCreate($params);
        } catch (\Throwable $e) {
            throw new ProviderException($e->getMessage(), $e);
        }
        $tokens = $resp->inputTokens + $resp->outputTokens;
        $toolCalls = 0;
        foreach ($resp->content as $b) {
            if ($b->type === 'tool_use') $toolCalls++;
        }
        $model = $resp->model !== '' ? $resp->model : 'unknown';
        $this->execution->recordStep(new StepInput(
            tokens: $tokens, toolCalls: $toolCalls,
            tag: "anthropic.messages.create:$model"));
        return $resp;
    }
}
