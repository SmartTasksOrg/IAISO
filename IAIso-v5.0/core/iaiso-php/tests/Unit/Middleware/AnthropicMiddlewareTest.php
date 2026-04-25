<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Middleware;

use IAIso\Audit\MemorySink;
use IAIso\Core\BoundedExecution;
use IAIso\Core\BoundedExecutionOptions;
use IAIso\Core\PressureConfig;
use IAIso\Core\StepInput;
use IAIso\Middleware\Anthropic\BoundedClient;
use IAIso\Middleware\Anthropic\Client;
use IAIso\Middleware\Anthropic\ContentBlock;
use IAIso\Middleware\Anthropic\Options;
use IAIso\Middleware\Anthropic\Response;
use IAIso\Middleware\EscalationRaisedException;
use PHPUnit\Framework\TestCase;

final class AnthropicMiddlewareTest extends TestCase
{
    public function testAccountsTokensAndToolCalls(): void
    {
        $sink = new MemorySink();
        $exec = BoundedExecution::start(new BoundedExecutionOptions(auditSink: $sink));

        $raw = new class implements Client {
            public function messagesCreate(array $params): Response
            {
                return new Response(
                    'claude-opus-4-7', 100, 250,
                    [
                        new ContentBlock('text'),
                        new ContentBlock('tool_use'),
                        new ContentBlock('tool_use'),
                    ],
                );
            }
        };
        $client = new BoundedClient($raw, $exec, Options::defaults());
        $client->messagesCreate([]);

        $foundStep = false;
        foreach ($sink->events() as $e) {
            if ($e->kind === 'engine.step') {
                self::assertSame(350, (int) $e->data['tokens']);
                self::assertSame(2, (int) $e->data['tool_calls']);
                $foundStep = true;
            }
        }
        self::assertTrue($foundStep, 'expected engine.step event');
        $exec->close();
    }

    public function testRaisesOnEscalationWhenOptedIn(): void
    {
        $cfg = PressureConfig::builder()
            ->escalationThreshold(0.4)->releaseThreshold(0.95)
            ->depthCoefficient(0.5)->dissipationPerStep(0.0)->build();
        $exec = BoundedExecution::start(new BoundedExecutionOptions(config: $cfg));
        $exec->recordStep(new StepInput(depth: 1));  // force escalation

        $raw = new class implements Client {
            public function messagesCreate(array $params): Response
            {
                return new Response('m', 0, 0, []);
            }
        };
        $client = new BoundedClient($raw, $exec, new Options(true));
        $this->expectException(EscalationRaisedException::class);
        $client->messagesCreate([]);
    }
}
