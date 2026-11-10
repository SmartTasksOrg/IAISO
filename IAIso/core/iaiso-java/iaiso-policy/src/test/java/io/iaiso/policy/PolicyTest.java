package io.iaiso.policy;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import org.junit.Test;

import java.util.HashMap;
import java.util.Map;

import static org.junit.Assert.*;

public class PolicyTest {

    @Test
    public void buildMinimalPolicy() {
        Policy p = PolicyLoader.build(JsonParser.parseString("{\"version\":\"1\"}"));
        assertEquals("1", p.getVersion());
        assertEquals("sum", p.getAggregator().name());
    }

    @Test
    public void buildOverridesDefaults() {
        String doc = "{\"version\":\"1\",\"pressure\":{\"escalation_threshold\":0.7,\"release_threshold\":0.85},\"coordinator\":{\"aggregator\":\"max\"}}";
        Policy p = PolicyLoader.build(JsonParser.parseString(doc));
        assertEquals(0.7, p.getPressure().getEscalationThreshold(), 1e-9);
        assertEquals("max", p.getAggregator().name());
    }

    @Test
    public void rejectsMissingVersion() {
        try {
            PolicyLoader.build(JsonParser.parseString("{}"));
            fail("expected exception");
        } catch (PolicyException e) {
            assertTrue(e.getMessage().contains("version"));
        }
    }

    @Test
    public void rejectsBadVersion() {
        try {
            PolicyLoader.build(JsonParser.parseString("{\"version\":\"2\"}"));
            fail();
        } catch (PolicyException expected) {}
    }

    @Test
    public void rejectsReleaseBelowEscalation() {
        try {
            PolicyLoader.build(JsonParser.parseString(
                "{\"version\":\"1\",\"pressure\":{\"escalation_threshold\":0.9,\"release_threshold\":0.5}}"));
            fail();
        } catch (PolicyException expected) {}
    }

    @Test
    public void sumAggregator() {
        Map<String, Double> m = new HashMap<>();
        m.put("a", 0.3); m.put("b", 0.5);
        assertEquals(0.8, new SumAggregator().aggregate(m), 1e-9);
    }

    @Test
    public void maxAggregator() {
        Map<String, Double> m = new HashMap<>();
        m.put("a", 0.3); m.put("b", 0.5);
        assertEquals(0.5, new MaxAggregator().aggregate(m), 1e-9);
    }

    @Test
    public void weightedSumAggregator() {
        Map<String, Double> w = new HashMap<>();
        w.put("important", 2.0);
        WeightedSumAggregator a = new WeightedSumAggregator(w, 1.0);
        Map<String, Double> p = new HashMap<>();
        p.put("important", 0.5); p.put("normal", 0.3);
        assertEquals(1.3, a.aggregate(p), 1e-9);
    }
}
