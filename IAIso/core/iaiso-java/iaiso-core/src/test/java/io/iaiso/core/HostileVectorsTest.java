package io.iaiso.core;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.ToNumberPolicy;
import io.iaiso.audit.MemorySink;
import org.junit.Test;

import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Collections;
import java.util.List;
import java.util.Map;

import static org.junit.Assert.*;

/** spec/pressure/hostile.json is shared by every IAIso port. */
public class HostileVectorsTest {

    private static final Gson GSON = new GsonBuilder()
        .setObjectToNumberStrategy(ToNumberPolicy.LONG_OR_DOUBLE).serializeNulls().create();

    @SuppressWarnings("unchecked")
    private static Map<String, Object> load() throws Exception {
        for (String c : new String[] {"spec/pressure/hostile.json", "../spec/pressure/hostile.json"}) {
            Path p = Paths.get(c);
            if (Files.exists(p)) {
                return GSON.fromJson(Files.readString(p), Map.class);
            }
        }
        throw new AssertionError("hostile.json not found from " + Paths.get("").toAbsolutePath());
    }

    private static PressureEngine engine() {
        Clock clk = () -> 0.0;
        return new PressureEngine(PressureConfig.defaults(),
            EngineOptions.builder().executionId("hostile").auditSink(new MemorySink())
                .clock(clk).timestampClock(clk).build());
    }

    @Test
    @SuppressWarnings("unchecked")
    public void hostileValuesAreRefused() throws Exception {
        List<Map<String, Object>> rejects = (List<Map<String, Object>>) load().get("reject");
        assertTrue(rejects.size() >= 18);
        for (Map<String, Object> v : rejects) {
            Map<String, Object> step = Collections.singletonMap((String) v.get("field"), v.get("value"));
            try {
                engine().step(StepInput.fromMap(step));
                fail(v.get("name") + ": accepted " + step);
            } catch (IllegalArgumentException expected) {
                // refused
            }
        }
    }

    @Test
    public void builderRefusesNegatives() {
        try {
            StepInput.builder().tokens(-40000).build();
            fail("negative tokens accepted");
        } catch (IllegalArgumentException expected) {
            // refused
        }
    }

    @Test
    @SuppressWarnings("unchecked")
    public void extremeValuesAreHandled() throws Exception {
        for (Map<String, Object> v : (List<Map<String, Object>>) load().get("accept")) {
            PressureEngine e = engine();
            StepOutcome out = e.step(StepInput.fromMap((Map<String, Object>) v.get("step")));
            Map<String, Object> exp = (Map<String, Object>) v.get("expect");
            assertFalse(Double.isNaN(e.getPressure()));
            assertEquals(v.get("name").toString(), ((Number) exp.get("pressure")).doubleValue(), e.getPressure(), 1e-9);
            assertEquals(v.get("name").toString(), exp.get("outcome"), out.toString());
            assertEquals(v.get("name").toString(), exp.get("lifecycle"), e.getLifecycle().toString());
        }
    }
}
