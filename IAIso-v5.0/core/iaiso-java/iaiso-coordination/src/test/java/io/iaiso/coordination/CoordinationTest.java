package io.iaiso.coordination;

import io.iaiso.audit.MemorySink;
import io.iaiso.policy.SumAggregator;
import org.junit.Test;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

public class CoordinationTest {

    @Test
    public void aggregatesSum() {
        SharedPressureCoordinator c = SharedPressureCoordinator.builder()
            .auditSink(new MemorySink())
            .build();
        c.register("a");
        c.register("b");
        c.update("a", 0.3);
        Snapshot snap = c.update("b", 0.5);
        assertEquals(0.8, snap.getAggregatePressure(), 1e-9);
    }

    @Test
    public void escalationCallbackFires() {
        AtomicInteger calls = new AtomicInteger(0);
        SharedPressureCoordinator c = SharedPressureCoordinator.builder()
            .escalationThreshold(0.7)
            .releaseThreshold(0.95)
            .notifyCooldownSeconds(0.0)
            .onEscalation(s -> calls.incrementAndGet())
            .build();
        c.register("a");
        c.update("a", 0.8);
        assertEquals(1, calls.get());
    }

    @Test
    public void rejectsBadPressure() {
        SharedPressureCoordinator c = SharedPressureCoordinator.builder().build();
        try { c.update("a", 1.5); fail(); } catch (CoordinatorException expected) {}
        try { c.update("a", -0.1); fail(); } catch (CoordinatorException expected) {}
    }

    @Test
    public void luaScriptUnchangedFromSpec() {
        assertTrue(RedisCoordinator.UPDATE_AND_FETCH_SCRIPT.contains("pressures_key = KEYS[1]"));
        assertTrue(RedisCoordinator.UPDATE_AND_FETCH_SCRIPT.contains("HGETALL"));
        assertTrue(RedisCoordinator.UPDATE_AND_FETCH_SCRIPT.contains("EXPIRE"));
    }

    @Test
    public void parseHGetAllFlatWorks() {
        List<String> reply = Arrays.asList("a", "0.3", "b", "0.5");
        Map<String, Double> out = RedisCoordinator.parseHGetAllFlat(reply);
        assertEquals(0.3, out.get("a"), 1e-9);
        assertEquals(0.5, out.get("b"), 1e-9);
    }

    /** Mock Redis for tests. */
    static class MockRedis implements RedisClient {
        Map<String, Map<String, String>> hashes = new TreeMap<>();

        @Override
        public Object eval(String script, String[] keys, String[] args) {
            String key = keys[0];
            Map<String, String> h = hashes.computeIfAbsent(key, k -> new TreeMap<>());
            if (script.contains("HSET") && script.contains("HGETALL")) {
                h.put(args[0], args[1]);
                List<String> flat = new ArrayList<>();
                for (Map.Entry<String, String> e : h.entrySet()) {
                    flat.add(e.getKey()); flat.add(e.getValue());
                }
                return flat;
            }
            if (script.contains("HDEL")) {
                h.remove(args[0]);
                return 1L;
            }
            return null;
        }

        @Override
        public void hset(String key, String[][] pairs) {
            Map<String, String> h = hashes.computeIfAbsent(key, k -> new TreeMap<>());
            for (String[] p : pairs) {
                h.put(p[0], p[1]);
            }
        }

        @Override
        public List<String> hkeys(String key) {
            Map<String, String> h = hashes.get(key);
            return h == null ? new ArrayList<>() : new ArrayList<>(h.keySet());
        }
    }

    @Test
    public void redisCoordinatorWithMock() {
        MockRedis mock = new MockRedis();
        RedisCoordinator c = RedisCoordinator.builder()
            .redis(mock)
            .coordinatorId("test")
            .escalationThreshold(0.7)
            .releaseThreshold(0.9)
            .pressuresTtlSeconds(300)
            .aggregator(new SumAggregator())
            .auditSink(new MemorySink())
            .clock(() -> 0.0)
            .build();
        c.register("a");
        c.register("b");
        c.update("a", 0.4);
        Snapshot snap = c.update("b", 0.3);
        assertEquals(0.7, snap.getAggregatePressure(), 1e-9);
    }
}
