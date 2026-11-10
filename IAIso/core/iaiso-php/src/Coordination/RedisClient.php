<?php

declare(strict_types=1);

namespace IAIso\Coordination;

/**
 * Structural Redis client interface. Implement this around your favorite
 * Redis library (phpredis, predis/predis, etc.) to plug it into
 * {@see RedisCoordinator}.
 */
interface RedisClient
{
    /**
     * Run a Lua script.
     *
     * @param string[] $keys
     * @param string[] $args
     * @return mixed parsed Redis reply (list, map, string, or int)
     */
    public function eval(string $script, array $keys, array $args): mixed;

    /**
     * HSET key field value [field value ...]
     *
     * @param array<int,array{0:string,1:string}> $fieldValuePairs
     */
    public function hset(string $key, array $fieldValuePairs): void;

    /**
     * HKEYS key
     *
     * @return string[]
     */
    public function hkeys(string $key): array;
}
