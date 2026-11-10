package io.iaiso.conformance;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.iaiso.audit.Event;
import io.iaiso.audit.MemorySink;
import io.iaiso.core.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

final class EventsRunner {
    static final double TOLERANCE = 1e-9;

    private EventsRunner() {}

    static List<VectorResult> run(Path specRoot) throws IOException {
        Path file = specRoot.resolve("events").resolve("vectors.json");
        JsonObject doc = JsonParser.parseString(
            new String(Files.readAllBytes(file))).getAsJsonObject();
        JsonArray vectors = doc.getAsJsonArray("vectors");
        List<VectorResult> out = new ArrayList<>();
        for (int i = 0; i < vectors.size(); i++) {
            out.add(runOne(vectors.get(i).getAsJsonObject()));
        }
        return out;
    }

    private static VectorResult runOne(JsonObject v) {
        String name = v.get("name").getAsString();
        PressureConfig.Builder cb = PressureConfig.builder();
        if (v.has("config") && v.get("config").isJsonObject()) {
            JsonObject c = v.getAsJsonObject("config");
            if (c.has("escalation_threshold")) cb.escalationThreshold(c.get("escalation_threshold").getAsDouble());
            if (c.has("release_threshold")) cb.releaseThreshold(c.get("release_threshold").getAsDouble());
            if (c.has("dissipation_per_step")) cb.dissipationPerStep(c.get("dissipation_per_step").getAsDouble());
            if (c.has("dissipation_per_second")) cb.dissipationPerSecond(c.get("dissipation_per_second").getAsDouble());
            if (c.has("token_coefficient")) cb.tokenCoefficient(c.get("token_coefficient").getAsDouble());
            if (c.has("tool_coefficient")) cb.toolCoefficient(c.get("tool_coefficient").getAsDouble());
            if (c.has("depth_coefficient")) cb.depthCoefficient(c.get("depth_coefficient").getAsDouble());
            if (c.has("post_release_lock")) cb.postReleaseLock(c.get("post_release_lock").getAsBoolean());
        }
        PressureConfig cfg = cb.build();

        double[] clockSeq;
        if (v.has("clock") && v.get("clock").isJsonArray()) {
            JsonArray arr = v.getAsJsonArray("clock");
            clockSeq = new double[arr.size()];
            for (int i = 0; i < arr.size(); i++) clockSeq[i] = arr.get(i).getAsDouble();
        } else {
            clockSeq = new double[]{0.0};
        }
        AtomicInteger idx = new AtomicInteger(0);
        Clock clk = () -> {
            int i = idx.getAndIncrement();
            return i < clockSeq.length ? clockSeq[i] : clockSeq[clockSeq.length - 1];
        };

        MemorySink sink = new MemorySink();
        String execId = v.get("execution_id").getAsString();
        PressureEngine engine;
        try {
            engine = new PressureEngine(cfg,
                EngineOptions.builder()
                    .executionId(execId)
                    .auditSink(sink)
                    .clock(clk).timestampClock(clk)
                    .build());
        } catch (RuntimeException e) {
            return VectorResult.fail("events", name, "engine init failed: " + e.getMessage());
        }

        Integer resetAfterStep = v.has("reset_after_step")
                && !v.get("reset_after_step").isJsonNull()
            ? v.get("reset_after_step").getAsInt() : null;

        JsonArray steps = v.has("steps") ? v.getAsJsonArray("steps") : new JsonArray();
        for (int i = 0; i < steps.size(); i++) {
            JsonObject step = steps.get(i).getAsJsonObject();
            if (step.has("reset") && step.get("reset").getAsBoolean()) {
                engine.reset();
            } else {
                StepInput.Builder sib = StepInput.builder();
                if (step.has("tokens")) sib.tokens(step.get("tokens").getAsLong());
                if (step.has("tool_calls")) sib.toolCalls(step.get("tool_calls").getAsLong());
                if (step.has("depth")) sib.depth(step.get("depth").getAsLong());
                if (step.has("tag") && !step.get("tag").isJsonNull())
                    sib.tag(step.get("tag").getAsString());
                engine.step(sib.build());
            }
            // 1-based: reset_after_step = N triggers after running step N
            if (resetAfterStep != null && (i + 1) == resetAfterStep) {
                engine.reset();
            }
        }

        List<Event> got = sink.events();
        JsonArray expected = v.getAsJsonArray("expected_events");
        if (got.size() != expected.size()) {
            return VectorResult.fail("events", name,
                "event count: got " + got.size() + ", want " + expected.size());
        }
        for (int i = 0; i < expected.size(); i++) {
            JsonObject exp = expected.get(i).getAsJsonObject();
            Event actual = got.get(i);
            if (exp.has("schema_version") && !exp.get("schema_version").isJsonNull()) {
                String sv = exp.get("schema_version").getAsString();
                if (!sv.isEmpty() && !sv.equals(actual.getSchemaVersion())) {
                    return VectorResult.fail("events", name,
                        "event " + i + " schema_version: got " + actual.getSchemaVersion()
                        + ", want " + sv);
                }
            }
            if (exp.has("execution_id") && !exp.get("execution_id").isJsonNull()) {
                String eid = exp.get("execution_id").getAsString();
                if (!eid.isEmpty() && !eid.equals(actual.getExecutionId())) {
                    return VectorResult.fail("events", name,
                        "event " + i + " execution_id: got " + actual.getExecutionId()
                        + ", want " + eid);
                }
            }
            if (!exp.get("kind").getAsString().equals(actual.getKind())) {
                return VectorResult.fail("events", name,
                    "event " + i + " kind: got " + actual.getKind()
                    + ", want " + exp.get("kind").getAsString());
            }
            if (exp.has("data") && exp.get("data").isJsonObject()) {
                JsonObject expData = exp.getAsJsonObject("data");
                if (!dataMatches(actual.getData(), expData)) {
                    return VectorResult.fail("events", name,
                        "event " + i + " data mismatch: got " + actual.getData()
                        + ", want " + expData);
                }
            }
        }
        return VectorResult.pass("events", name);
    }

    /** Loose equality: missing keys treated as null; numbers compared with tolerance. */
    private static boolean dataMatches(java.util.Map<String, Object> actual, JsonObject want) {
        for (var entry : want.entrySet()) {
            Object got = actual.get(entry.getKey());
            JsonElement w = entry.getValue();
            if (!valueEqual(got, w)) return false;
        }
        return true;
    }

    private static boolean valueEqual(Object actual, JsonElement want) {
        if (want.isJsonNull()) return actual == null;
        if (actual == null) return false;
        if (want.isJsonPrimitive()) {
            var p = want.getAsJsonPrimitive();
            if (p.isBoolean()) {
                return actual instanceof Boolean && ((Boolean) actual) == p.getAsBoolean();
            }
            if (p.isNumber()) {
                if (actual instanceof Number) {
                    return Math.abs(((Number) actual).doubleValue() - p.getAsDouble())
                        <= TOLERANCE;
                }
                return false;
            }
            if (p.isString()) {
                return actual instanceof String && actual.equals(p.getAsString());
            }
        }
        if (want.isJsonArray()) {
            if (!(actual instanceof java.util.List)) return false;
            java.util.List<?> aList = (java.util.List<?>) actual;
            JsonArray wArr = want.getAsJsonArray();
            if (aList.size() != wArr.size()) return false;
            for (int i = 0; i < wArr.size(); i++) {
                if (!valueEqual(aList.get(i), wArr.get(i))) return false;
            }
            return true;
        }
        if (want.isJsonObject()) {
            if (!(actual instanceof java.util.Map)) return false;
            JsonObject wObj = want.getAsJsonObject();
            for (var e : wObj.entrySet()) {
                Object got = ((java.util.Map<?, ?>) actual).get(e.getKey());
                if (!valueEqual(got, e.getValue())) return false;
            }
            return true;
        }
        return false;
    }
}
