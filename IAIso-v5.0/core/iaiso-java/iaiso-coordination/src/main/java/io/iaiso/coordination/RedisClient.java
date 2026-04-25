package io.iaiso.coordination;

/**
 * Structural Redis client interface. Implement this around your favorite
 * Redis library (Jedis, Lettuce, Spring Data Redis, etc.) to plug it
 * into {@link RedisCoordinator}.
 */
public interface RedisClient {

    /** Run a Lua script. Returns a parsed Redis reply. */
    Object eval(String script, String[] keys, String[] args);

    /** HSET key field value [field value ...] */
    void hset(String key, String[][] fieldValuePairs);

    /** HKEYS key */
    java.util.List<String> hkeys(String key);
}
