package io.iaiso.conformance;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.iaiso.audit.NullSink;
import io.iaiso.core.*;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

final class PressureRunner {
    static final double TOLERANCE = 1e-9;

    private PressureRunner() {}

    static List<VectorResult> run(Path specRoot) throws IOException {
        Path file = specRoot.resolve("pressure").resolve("vectors.json");
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
        if (v.has("config")) {
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

        // Scripted clock
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

        // Expect config error?
        String expectErr = v.has("expect_config_error") && !v.get("expect_config_error").isJsonNull()
            ? v.get("expect_config_error").getAsString() : null;
        PressureEngine engine;
        try {
            engine = new PressureEngine(cfg,
                EngineOptions.builder()
                    .executionId("vec-" + name)
                    .auditSink(NullSink.INSTANCE)
                    .clock(clk).timestampClock(clk)
                    .build());
        } catch (ConfigException e) {
            if (expectErr == null) {
                return VectorResult.fail("pressure", name,
                    "engine construction failed: " + e.getMessage());
            }
            if (!e.getMessage().contains(expectErr)) {
                return VectorResult.fail("pressure", name,
                    "expected error containing '" + expectErr + "', got: " + e.getMessage());
            }
            return VectorResult.pass("pressure", name);
        }
        if (expectErr != null) {
            return VectorResult.fail("pressure", name,
                "expected config error containing '" + expectErr + "', got Ok");
        }

        // expected_initial
        if (v.has("expected_initial") && v.get("expected_initial").isJsonObject()) {
            JsonObject init = v.getAsJsonObject("expected_initial");
            PressureSnapshot snap = engine.snapshot();
            if (Math.abs(snap.getPressure() - init.get("pressure").getAsDouble()) > TOLERANCE) {
                return VectorResult.fail("pressure", name,
                    "initial pressure: got " + snap.getPressure()
                    + ", want " + init.get("pressure").getAsDouble());
            }
            if (snap.getStep() != init.get("step").getAsLong()) {
                return VectorResult.fail("pressure", name,
                    "initial step: got " + snap.getStep()
                    + ", want " + init.get("step").getAsLong());
            }
            if (!snap.getLifecycle().toString().equals(init.get("lifecycle").getAsString())) {
                return VectorResult.fail("pressure", name,
                    "initial lifecycle: got " + snap.getLifecycle()
                    + ", want " + init.get("lifecycle").getAsString());
            }
            if (Math.abs(snap.getLastStepAt() - init.get("last_step_at").getAsDouble()) > TOLERANCE) {
                return VectorResult.fail("pressure", name,
                    "initial last_step_at: got " + snap.getLastStepAt()
                    + ", want " + init.get("last_step_at").getAsDouble());
            }
        }

        JsonArray steps = v.has("steps") ? v.getAsJsonArray("steps") : new JsonArray();
        JsonArray expSteps = v.has("expected_steps")
            ? v.getAsJsonArray("expected_steps") : new JsonArray();
        for (int i = 0; i < steps.size(); i++) {
            JsonObject step = steps.get(i).getAsJsonObject();
            StepOutcome outcome;
            if (step.has("reset") && step.get("reset").getAsBoolean()) {
                engine.reset();
                outcome = StepOutcome.OK;
            } else {
                StepInput.Builder sib = StepInput.builder();
                if (step.has("tokens")) sib.tokens(step.get("tokens").getAsLong());
                if (step.has("tool_calls")) sib.toolCalls(step.get("tool_calls").getAsLong());
                if (step.has("depth")) sib.depth(step.get("depth").getAsLong());
                if (step.has("tag") && !step.get("tag").isJsonNull())
                    sib.tag(step.get("tag").getAsString());
                outcome = engine.step(sib.build());
            }
            if (i >= expSteps.size()) {
                return VectorResult.fail("pressure", name,
                    "step " + i + ": no expected entry");
            }
            JsonObject exp = expSteps.get(i).getAsJsonObject();
            if (!outcome.toString().equals(exp.get("outcome").getAsString())) {
                return VectorResult.fail("pressure", name,
                    "step " + i + ": outcome got " + outcome + ", want " + exp.get("outcome"));
            }
            PressureSnapshot snap = engine.snapshot();
            if (Math.abs(snap.getPressure() - exp.get("pressure").getAsDouble()) > TOLERANCE) {
                return VectorResult.fail("pressure", name,
                    "step " + i + ": pressure got " + snap.getPressure()
                    + ", want " + exp.get("pressure").getAsDouble());
            }
            if (snap.getStep() != exp.get("step").getAsLong()) {
                return VectorResult.fail("pressure", name,
                    "step " + i + ": step got " + snap.getStep()
                    + ", want " + exp.get("step").getAsLong());
            }
            if (!snap.getLifecycle().toString().equals(exp.get("lifecycle").getAsString())) {
                return VectorResult.fail("pressure", name,
                    "step " + i + ": lifecycle got " + snap.getLifecycle()
                    + ", want " + exp.get("lifecycle"));
            }
        }
        return VectorResult.pass("pressure", name);
    }
}
