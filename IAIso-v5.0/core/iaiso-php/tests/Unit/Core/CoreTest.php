<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Core;

use IAIso\Audit\MemorySink;
use IAIso\Core\BoundedExecution;
use IAIso\Core\BoundedExecutionOptions;
use IAIso\Core\ConfigException;
use IAIso\Core\EngineOptions;
use IAIso\Core\Lifecycle;
use IAIso\Core\PressureConfig;
use IAIso\Core\PressureEngine;
use IAIso\Core\ScriptedClock;
use IAIso\Core\StepInput;
use IAIso\Core\StepOutcome;
use PHPUnit\Framework\TestCase;

final class CoreTest extends TestCase
{
    public function testEnumWireValuesMatchSpec(): void
    {
        self::assertSame('init', Lifecycle::Init->value);
        self::assertSame('running', Lifecycle::Running->value);
        self::assertSame('escalated', Lifecycle::Escalated->value);
        self::assertSame('released', Lifecycle::Released->value);
        self::assertSame('locked', Lifecycle::Locked->value);
        self::assertSame('ok', StepOutcome::Ok->value);
    }

    public function testConfigRejectsBadThresholds(): void
    {
        $cfg = PressureConfig::builder()->escalationThreshold(0.9)->releaseThreshold(0.5)->build();
        $this->expectException(ConfigException::class);
        $cfg->validate();
    }

    public function testConfigRejectsNegativeCoefficient(): void
    {
        $cfg = PressureConfig::builder()->tokenCoefficient(-1.0)->build();
        $this->expectException(ConfigException::class);
        $cfg->validate();
    }

    public function testEngineEscalatesOnHighPressure(): void
    {
        $sink = new MemorySink();
        $clk = new ScriptedClock([0.0, 1.0]);
        $cfg = PressureConfig::builder()
            ->escalationThreshold(0.5)->releaseThreshold(0.95)
            ->dissipationPerStep(0.0)->depthCoefficient(0.6)->build();
        $eng = new PressureEngine($cfg, new EngineOptions('e', $sink, $clk, $clk));
        $outcome = $eng->step(new StepInput(depth: 1));
        self::assertSame(StepOutcome::Escalated, $outcome);
        self::assertEqualsWithDelta(0.6, $eng->getPressure(), 1e-9);
    }

    public function testEngineLocksAfterRelease(): void
    {
        $clk = new ScriptedClock([0.0, 1.0, 2.0]);
        $cfg = PressureConfig::builder()
            ->escalationThreshold(0.5)->releaseThreshold(0.9)
            ->dissipationPerStep(0.0)->depthCoefficient(1.0)
            ->postReleaseLock(true)->build();
        $eng = new PressureEngine($cfg, new EngineOptions('e', null, $clk, $clk));
        $eng->step(new StepInput(depth: 1)); // pressure → 1.0 → release → lock
        self::assertSame(Lifecycle::Locked, $eng->getLifecycle());
        $next = $eng->step(new StepInput(depth: 1));
        self::assertSame(StepOutcome::Locked, $next);
    }

    public function testEngineResetEmitsResetEvent(): void
    {
        $sink = new MemorySink();
        $clk = new ScriptedClock([0.0, 1.0, 2.0]);
        $cfg = PressureConfig::defaults();
        $eng = new PressureEngine($cfg, new EngineOptions('e', $sink, $clk, $clk));
        $eng->step(new StepInput(tokens: 100));
        $eng->reset();
        $kinds = array_map(fn($e) => $e->kind, $sink->events());
        self::assertContains('engine.reset', $kinds);
        self::assertSame(0.0, $eng->getPressure());
        self::assertSame(Lifecycle::Init, $eng->getLifecycle());
    }

    public function testBoundedExecutionRunEmitsClosed(): void
    {
        $sink = new MemorySink();
        BoundedExecution::run(
            new BoundedExecutionOptions(executionId: 'e1', auditSink: $sink),
            function ($ex): void { $ex->recordTokens(100, 'x'); },
        );
        $kinds = array_map(fn($e) => $e->kind, $sink->events());
        self::assertContains('execution.closed', $kinds);
    }

    public function testBoundedExecutionAutoIdWhenEmpty(): void
    {
        $sink = new MemorySink();
        BoundedExecution::run(
            new BoundedExecutionOptions(auditSink: $sink),
            function ($ex): void {},
        );
        self::assertNotEmpty($sink->events());
        self::assertStringStartsWith('exec-', $sink->events()[0]->executionId);
    }

    public function testRecordToolCallAdvancesEngine(): void
    {
        $exec = BoundedExecution::start(new BoundedExecutionOptions());
        $outcome = $exec->recordToolCall('search', 100);
        self::assertSame(StepOutcome::Ok, $outcome);
        self::assertGreaterThan(0.0, $exec->snapshot()->pressure);
        $exec->close();
    }
}
