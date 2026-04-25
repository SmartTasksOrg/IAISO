<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Coordination;

use IAIso\Audit\MemorySink;
use IAIso\Coordination\CoordinatorException;
use IAIso\Coordination\RedisClient;
use IAIso\Coordination\RedisCoordinator;
use IAIso\Coordination\SharedPressureCoordinator;
use IAIso\Coordination\Snapshot;
use IAIso\Policy\SumAggregator;
use PHPUnit\Framework\TestCase;

final class CoordinationTest extends TestCase
{
    public function testAggregatesSum(): void
    {
        $c = SharedPressureCoordinator::builder()
            ->auditSink(new MemorySink())->build();
        $c->register('a');
        $c->register('b');
        $c->update('a', 0.3);
        $snap = $c->update('b', 0.5);
        self::assertEqualsWithDelta(0.8, $snap->aggregatePressure, 1e-9);
    }

    public function testEscalationCallbackFires(): void
    {
        $calls = 0;
        $c = SharedPressureCoordinator::builder()
            ->escalationThreshold(0.7)->releaseThreshold(0.95)
            ->notifyCooldownSeconds(0.0)
            ->onEscalation(function ($s) use (&$calls): void { $calls++; })
            ->build();
        $c->register('a');
        $c->update('a', 0.8);
        self::assertSame(1, $calls);
    }

    public function testRejectsBadPressure(): void
    {
        $c = SharedPressureCoordinator::builder()->build();
        $this->expectException(CoordinatorException::class);
        $c->update('a', 1.5);
    }

    public function testLuaScriptUnchangedFromSpec(): void
    {
        self::assertStringContainsString('pressures_key = KEYS[1]', RedisCoordinator::UPDATE_AND_FETCH_SCRIPT);
        self::assertStringContainsString('HGETALL', RedisCoordinator::UPDATE_AND_FETCH_SCRIPT);
        self::assertStringContainsString('EXPIRE', RedisCoordinator::UPDATE_AND_FETCH_SCRIPT);
    }

    public function testParseHGetAllFlatWorks(): void
    {
        $reply = ['a', '0.3', 'b', '0.5'];
        $out = RedisCoordinator::parseHGetAllFlat($reply);
        self::assertEqualsWithDelta(0.3, $out['a'], 1e-9);
        self::assertEqualsWithDelta(0.5, $out['b'], 1e-9);
    }

    public function testRedisCoordinatorWithMock(): void
    {
        $mock = new MockRedis();
        $c = RedisCoordinator::builder()
            ->redis($mock)->coordinatorId('test')
            ->escalationThreshold(0.7)->releaseThreshold(0.9)
            ->pressuresTtlSeconds(300)
            ->aggregator(new SumAggregator())
            ->auditSink(new MemorySink())
            ->build();
        $c->register('a');
        $c->register('b');
        $c->update('a', 0.4);
        $snap = $c->update('b', 0.3);
        self::assertEqualsWithDelta(0.7, $snap->aggregatePressure, 1e-9);
    }
}

/** Minimal in-memory Redis mock for tests. */
final class MockRedis implements RedisClient
{
    /** @var array<string,array<string,string>> */
    private array $hashes = [];

    public function eval(string $script, array $keys, array $args): mixed
    {
        $key = $keys[0];
        $this->hashes[$key] ??= [];
        if (str_contains($script, 'HSET') && str_contains($script, 'HGETALL')) {
            $this->hashes[$key][$args[0]] = $args[1];
            $flat = [];
            foreach ($this->hashes[$key] as $k => $v) {
                $flat[] = $k;
                $flat[] = $v;
            }
            return $flat;
        }
        if (str_contains($script, 'HDEL')) {
            unset($this->hashes[$key][$args[0]]);
            return 1;
        }
        return null;
    }

    public function hset(string $key, array $pairs): void
    {
        $this->hashes[$key] ??= [];
        foreach ($pairs as $p) {
            $this->hashes[$key][$p[0]] = $p[1];
        }
    }

    public function hkeys(string $key): array
    {
        return array_keys($this->hashes[$key] ?? []);
    }
}
