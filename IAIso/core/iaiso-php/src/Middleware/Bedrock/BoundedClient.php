<?php

declare(strict_types=1);

namespace IAIso\Middleware\Bedrock;

use IAIso\Core\BoundedExecution;
use IAIso\Core\StepInput;
use IAIso\Core\StepOutcome;
use IAIso\Middleware\EscalationRaisedException;
use IAIso\Middleware\LockedException;
use IAIso\Middleware\ProviderException;

/**
 * IAIso wrapper for AWS Bedrock runtime. Supports both Converse API
 * (preferred — normalized usage extraction) and the lower-level
 * InvokeModel API.
 */
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
    public function converse(array $params): ConverseResponse
    {
        $this->checkState();
        try {
            $resp = $this->raw->converse($params);
        } catch (\Throwable $e) {
            throw new ProviderException($e->getMessage(), $e);
        }
        $tokens = $resp->usage->totalTokens;
        if ($tokens === 0) $tokens = $resp->usage->inputTokens + $resp->usage->outputTokens;
        $toolCalls = 0;
        foreach ($resp->content as $b) {
            if ($b->hasToolUse) $toolCalls++;
        }
        $modelId = $params['modelId'] ?? 'unknown';
        $this->execution->recordStep(new StepInput(
            tokens: $tokens, toolCalls: $toolCalls,
            tag: "bedrock.converse:$modelId"));
        return $resp;
    }

    /** @param array<string,mixed> $params */
    public function invokeModel(array $params): InvokeResponse
    {
        $this->checkState();
        try {
            $resp = $this->raw->invokeModel($params);
        } catch (\Throwable $e) {
            throw new ProviderException($e->getMessage(), $e);
        }
        $modelId = $resp->modelId !== ''
            ? $resp->modelId : ($params['modelId'] ?? 'unknown');
        // Best-effort: model-specific bodies require the user's adapter
        // to extract token counts. Default to 0; users may add a
        // recordTokens() call with the parsed value if needed.
        $this->execution->recordStep(new StepInput(
            tag: "bedrock.invokeModel:$modelId"));
        return $resp;
    }

    private function checkState(): void
    {
        $pre = $this->execution->check();
        if ($pre === StepOutcome::Locked) throw new LockedException();
        if ($pre === StepOutcome::Escalated && $this->opts->raiseOnEscalation) {
            throw new EscalationRaisedException();
        }
    }
}
