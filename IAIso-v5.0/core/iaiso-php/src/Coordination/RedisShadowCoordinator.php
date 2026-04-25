<?php

declare(strict_types=1);

namespace IAIso\Coordination;

/**
 * Internal helper: a {@see SharedPressureCoordinator} subclass that
 * exposes the protected {@code setPressuresFromMap} and
 * {@code evaluate} methods so {@see RedisCoordinator} can drive its
 * lifecycle from external Redis state.
 *
 * @internal
 */
final class RedisShadowCoordinator extends SharedPressureCoordinator
{
    /** @param array<string,float> $updated */
    public function setPressuresFromMapPublic(array $updated): void
    {
        $this->setPressuresFromMap($updated);
    }

    public function evaluatePublic(): Snapshot
    {
        return $this->evaluate();
    }
}
