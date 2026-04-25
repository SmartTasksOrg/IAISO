<?php

declare(strict_types=1);

namespace IAIso\Coordination;

use IAIso\Audit\Event;
use IAIso\Audit\NullSink;
use IAIso\Audit\Sink;
use IAIso\Core\Clock;
use IAIso\Core\WallClock;
use IAIso\Policy\Aggregator;
use IAIso\Policy\SumAggregator;

/**
 * Redis-backed coordinator. Interoperable with the Python, Node, Go,
 * Rust, Java, and C# references via the shared keyspace and the
 * verbatim Lua script in {@see self::UPDATE_AND_FETCH_SCRIPT}.
 */
final class RedisCoordinator
{
    /**
     * The normative Lua script — verbatim from
     * {@code spec/coordinator/README.md §1.2}. Bytes are identical
     * across all reference SDKs to ensure cross-language fleet
     * coordination.
     */
    public const UPDATE_AND_FETCH_SCRIPT =
        "\nlocal pressures_key = KEYS[1]\n"
      . "local exec_id       = ARGV[1]\n"
      . "local new_pressure  = ARGV[2]\n"
      . "local ttl_seconds   = tonumber(ARGV[3])\n"
      . "\n"
      . "redis.call('HSET', pressures_key, exec_id, new_pressure)\n"
      . "if ttl_seconds > 0 then\n"
      . "  redis.call('EXPIRE', pressures_key, ttl_seconds)\n"
      . "end\n"
      . "\n"
      . "return redis.call('HGETALL', pressures_key)\n";

    private readonly RedisClient $redis;
    private readonly string $keyPrefix;
    private readonly int $pressuresTtlSeconds;
    private readonly RedisShadowCoordinator $shadow;
    private readonly Sink $auditSink;
    private readonly Clock $clock;

    public function __construct(
        RedisClient $redis,
        string $coordinatorId = 'default',
        float $escalationThreshold = 5.0,
        float $releaseThreshold = 8.0,
        float $notifyCooldownSeconds = 1.0,
        string $keyPrefix = 'iaiso:coord',
        int $pressuresTtlSeconds = 300,
        ?Aggregator $aggregator = null,
        ?Sink $auditSink = null,
        ?callable $onEscalation = null,
        ?callable $onRelease = null,
        ?Clock $clock = null,
    ) {
        $this->redis = $redis;
        $this->keyPrefix = $keyPrefix;
        $this->pressuresTtlSeconds = $pressuresTtlSeconds;
        $this->auditSink = $auditSink ?? NullSink::instance();
        $this->clock = $clock ?? WallClock::instance();
        $aggregator = $aggregator ?? new SumAggregator();
        $this->shadow = new RedisShadowCoordinator(
            $coordinatorId, $escalationThreshold, $releaseThreshold,
            $notifyCooldownSeconds, $aggregator, NullSink::instance(),
            $onEscalation, $onRelease, $this->clock, false,
        );
        $this->auditSink->emit(new Event(
            'coord:' . $coordinatorId,
            'coordinator.init',
            $this->clock->now(),
            [
                'coordinator_id' => $coordinatorId,
                'aggregator'     => $aggregator->name(),
                'backend'        => 'redis',
            ],
        ));
    }

    public static function builder(): RedisCoordinatorBuilder
    {
        return new RedisCoordinatorBuilder();
    }

    private function pressuresKey(): string
    {
        return $this->keyPrefix . ':' . $this->shadow->getCoordinatorId() . ':pressures';
    }

    public function register(string $executionId): Snapshot
    {
        $this->redis->hset($this->pressuresKey(), [[$executionId, '0.0']]);
        return $this->shadow->register($executionId);
    }

    public function unregister(string $executionId): Snapshot
    {
        $this->redis->eval(
            "redis.call('HDEL', KEYS[1], ARGV[1]); return 1",
            [$this->pressuresKey()],
            [$executionId],
        );
        return $this->shadow->unregister($executionId);
    }

    public function update(string $executionId, float $pressure): Snapshot
    {
        if ($pressure < 0.0 || $pressure > 1.0) {
            throw new CoordinatorException("pressure must be in [0, 1], got $pressure");
        }
        $reply = $this->redis->eval(
            self::UPDATE_AND_FETCH_SCRIPT,
            [$this->pressuresKey()],
            [$executionId, (string) $pressure, (string) $this->pressuresTtlSeconds],
        );
        $updated = self::parseHGetAllFlat($reply);
        $this->shadow->setPressuresFromMapPublic($updated);
        return $this->shadow->evaluatePublic();
    }

    public function reset(): int
    {
        $keys = $this->redis->hkeys($this->pressuresKey());
        if (count($keys) > 0) {
            $pairs = array_map(fn($k) => [(string) $k, '0.0'], $keys);
            $this->redis->hset($this->pressuresKey(), $pairs);
        }
        return $this->shadow->reset();
    }

    public function snapshot(): Snapshot
    {
        return $this->shadow->snapshot();
    }

    /**
     * Parse a flat HGETALL Redis reply into a string→float map.
     * Accepts either a flat list (standard) or an associative array.
     *
     * @return array<string,float>
     */
    public static function parseHGetAllFlat(mixed $reply): array
    {
        $out = [];
        if (!is_array($reply)) {
            return $out;
        }
        if (!array_is_list($reply)) {
            // Associative
            foreach ($reply as $k => $v) {
                $out[(string) $k] = (float) $v;
            }
            return $out;
        }
        // Flat list: [k0, v0, k1, v1, ...]
        $count = count($reply);
        for ($i = 0; $i + 1 < $count; $i += 2) {
            $out[(string) $reply[$i]] = (float) $reply[$i + 1];
        }
        return $out;
    }
}
