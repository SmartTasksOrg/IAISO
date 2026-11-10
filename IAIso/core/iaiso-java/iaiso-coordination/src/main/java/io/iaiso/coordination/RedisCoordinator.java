package io.iaiso.coordination;

import io.iaiso.audit.Event;
import io.iaiso.audit.NullSink;
import io.iaiso.audit.Sink;
import io.iaiso.policy.Aggregator;
import io.iaiso.policy.SumAggregator;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.function.Consumer;

/**
 * Redis-backed coordinator. Interoperable with the Python, Node, Go,
 * and Rust references via the shared keyspace and the verbatim Lua
 * script in {@link #UPDATE_AND_FETCH_SCRIPT}.
 */
public final class RedisCoordinator {

    /**
     * The normative Lua script — verbatim from
     * {@code spec/coordinator/README.md §1.2}. Bytes are identical
     * across all reference SDKs to ensure cross-language fleet
     * coordination.
     */
    public static final String UPDATE_AND_FETCH_SCRIPT =
        "\nlocal pressures_key = KEYS[1]\n"
        + "local exec_id       = ARGV[1]\n"
        + "local new_pressure  = ARGV[2]\n"
        + "local ttl_seconds   = tonumber(ARGV[3])\n"
        + "\n"
        + "redis.call('HSET', pressures_key, exec_id, new_pressure)\n"
        + "if ttl_seconds > 0 then\n"
        + "  redis.call('EXPIRE', pressures_key, ttl_seconds)\n"
        + "end\n"
        + "\n"
        + "return redis.call('HGETALL', pressures_key)\n";

    private final RedisClient redis;
    private final String keyPrefix;
    private final long pressuresTtlSeconds;
    private final SharedPressureCoordinator shadow;
    private final Sink auditSink;
    private final SharedPressureCoordinator.Clock clock;

    private RedisCoordinator(Builder b) {
        this.redis = b.redis;
        this.keyPrefix = b.keyPrefix;
        this.pressuresTtlSeconds = b.pressuresTtlSeconds;
        this.auditSink = b.auditSink != null ? b.auditSink : NullSink.INSTANCE;
        this.clock = b.clock != null ? b.clock : SharedPressureCoordinator.Clock.wallclock();
        this.shadow = new SharedPressureCoordinator(b.coordinatorId,
            b.escalationThreshold, b.releaseThreshold, b.notifyCooldownSeconds,
            b.aggregator, NullSink.INSTANCE, b.onEscalation, b.onRelease, this.clock, false);
        // Emit init with backend=redis using the user's audit sink.
        Map<String, Object> data = new LinkedHashMap<>();
        data.put("coordinator_id", b.coordinatorId);
        data.put("aggregator", b.aggregator.name());
        data.put("backend", "redis");
        Event e = new Event("coord:" + b.coordinatorId,
            "coordinator.init", this.clock.now(), data);
        this.auditSink.emit(e);
    }

    public static Builder builder() { return new Builder(); }

    private String pressuresKey() {
        return keyPrefix + ":" + shadow.getCoordinatorId() + ":pressures";
    }

    public Snapshot register(String executionId) {
        redis.hset(pressuresKey(), new String[][]{{executionId, "0.0"}});
        return shadow.register(executionId);
    }

    public Snapshot unregister(String executionId) {
        redis.eval("redis.call('HDEL', KEYS[1], ARGV[1]); return 1",
            new String[]{pressuresKey()}, new String[]{executionId});
        return shadow.unregister(executionId);
    }

    public Snapshot update(String executionId, double pressure) {
        if (pressure < 0.0 || pressure > 1.0) {
            throw new CoordinatorException(
                "pressure must be in [0, 1], got " + pressure);
        }
        Object result = redis.eval(UPDATE_AND_FETCH_SCRIPT,
            new String[]{pressuresKey()},
            new String[]{executionId, Double.toString(pressure),
                Long.toString(pressuresTtlSeconds)});
        Map<String, Double> updated = parseHGetAllFlat(result);
        shadow.setPressuresFromMap(updated);
        return shadow.evaluate();
    }

    public int reset() {
        List<String> keys = redis.hkeys(pressuresKey());
        if (!keys.isEmpty()) {
            String[][] pairs = new String[keys.size()][2];
            for (int i = 0; i < keys.size(); i++) {
                pairs[i][0] = keys.get(i);
                pairs[i][1] = "0.0";
            }
            redis.hset(pressuresKey(), pairs);
        }
        return shadow.reset();
    }

    public Snapshot snapshot() {
        return shadow.snapshot();
    }

    /**
     * Parse a flat HGETALL Redis reply into a string→double map.
     * Accepts either a {@code List<Object>} (standard Redis driver) or a
     * pre-parsed {@code Map}.
     */
    @SuppressWarnings("unchecked")
    public static Map<String, Double> parseHGetAllFlat(Object reply) {
        Map<String, Double> out = new TreeMap<>();
        if (reply == null) {
            return out;
        }
        if (reply instanceof Map) {
            for (Map.Entry<Object, Object> e : ((Map<Object, Object>) reply).entrySet()) {
                String k = String.valueOf(e.getKey());
                try {
                    out.put(k, Double.parseDouble(String.valueOf(e.getValue())));
                } catch (NumberFormatException ignored) {}
            }
            return out;
        }
        if (reply instanceof List) {
            List<?> list = (List<?>) reply;
            for (int i = 0; i + 1 < list.size(); i += 2) {
                String k = String.valueOf(list.get(i));
                try {
                    out.put(k, Double.parseDouble(String.valueOf(list.get(i + 1))));
                } catch (NumberFormatException ignored) {}
            }
        }
        return out;
    }

    public static final class Builder {
        RedisClient redis;
        String coordinatorId = "default";
        double escalationThreshold = 5.0;
        double releaseThreshold = 8.0;
        double notifyCooldownSeconds = 1.0;
        String keyPrefix = "iaiso:coord";
        long pressuresTtlSeconds = 300L;
        Aggregator aggregator = new SumAggregator();
        Sink auditSink;
        Consumer<Snapshot> onEscalation;
        Consumer<Snapshot> onRelease;
        SharedPressureCoordinator.Clock clock;

        public Builder redis(RedisClient v) { this.redis = v; return this; }
        public Builder coordinatorId(String v) { this.coordinatorId = v; return this; }
        public Builder escalationThreshold(double v) { this.escalationThreshold = v; return this; }
        public Builder releaseThreshold(double v) { this.releaseThreshold = v; return this; }
        public Builder notifyCooldownSeconds(double v) { this.notifyCooldownSeconds = v; return this; }
        public Builder keyPrefix(String v) { this.keyPrefix = v; return this; }
        public Builder pressuresTtlSeconds(long v) { this.pressuresTtlSeconds = v; return this; }
        public Builder aggregator(Aggregator v) { this.aggregator = v; return this; }
        public Builder auditSink(Sink v) { this.auditSink = v; return this; }
        public Builder onEscalation(Consumer<Snapshot> v) { this.onEscalation = v; return this; }
        public Builder onRelease(Consumer<Snapshot> v) { this.onRelease = v; return this; }
        public Builder clock(SharedPressureCoordinator.Clock v) { this.clock = v; return this; }

        public RedisCoordinator build() {
            if (redis == null) {
                throw new CoordinatorException("redis is required");
            }
            return new RedisCoordinator(this);
        }
    }
}
