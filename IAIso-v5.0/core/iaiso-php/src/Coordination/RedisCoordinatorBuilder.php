<?php

declare(strict_types=1);

namespace IAIso\Coordination;

use IAIso\Audit\Sink;
use IAIso\Core\Clock;
use IAIso\Policy\Aggregator;
use IAIso\Policy\SumAggregator;

/** Builder for {@see RedisCoordinator}. */
final class RedisCoordinatorBuilder
{
    private ?RedisClient $redis = null;
    private string $coordinatorId = 'default';
    private float $escalationThreshold = 5.0;
    private float $releaseThreshold = 8.0;
    private float $notifyCooldownSeconds = 1.0;
    private string $keyPrefix = 'iaiso:coord';
    private int $pressuresTtlSeconds = 300;
    private ?Aggregator $aggregator = null;
    private ?Sink $auditSink = null;
    /** @var (callable(Snapshot):void)|null */
    private $onEscalation = null;
    /** @var (callable(Snapshot):void)|null */
    private $onRelease = null;
    private ?Clock $clock = null;

    public function redis(RedisClient $r): self             { $this->redis = $r; return $this; }
    public function coordinatorId(string $v): self          { $this->coordinatorId = $v; return $this; }
    public function escalationThreshold(float $v): self     { $this->escalationThreshold = $v; return $this; }
    public function releaseThreshold(float $v): self        { $this->releaseThreshold = $v; return $this; }
    public function notifyCooldownSeconds(float $v): self   { $this->notifyCooldownSeconds = $v; return $this; }
    public function keyPrefix(string $v): self              { $this->keyPrefix = $v; return $this; }
    public function pressuresTtlSeconds(int $v): self       { $this->pressuresTtlSeconds = $v; return $this; }
    public function aggregator(Aggregator $a): self         { $this->aggregator = $a; return $this; }
    public function auditSink(?Sink $s): self               { $this->auditSink = $s; return $this; }
    public function clock(?Clock $c): self                  { $this->clock = $c; return $this; }

    /** @param callable(Snapshot):void $cb */
    public function onEscalation(callable $cb): self        { $this->onEscalation = $cb; return $this; }

    /** @param callable(Snapshot):void $cb */
    public function onRelease(callable $cb): self           { $this->onRelease = $cb; return $this; }

    public function build(): RedisCoordinator
    {
        if ($this->redis === null) {
            throw new CoordinatorException('redis is required');
        }
        return new RedisCoordinator(
            $this->redis, $this->coordinatorId, $this->escalationThreshold,
            $this->releaseThreshold, $this->notifyCooldownSeconds,
            $this->keyPrefix, $this->pressuresTtlSeconds,
            $this->aggregator ?? new SumAggregator(), $this->auditSink,
            $this->onEscalation, $this->onRelease, $this->clock,
        );
    }
}
