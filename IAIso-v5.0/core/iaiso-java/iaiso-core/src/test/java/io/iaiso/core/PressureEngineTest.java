package io.iaiso.core;

import io.iaiso.audit.Event;
import io.iaiso.audit.MemorySink;
import org.junit.Test;

import java.util.Arrays;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import static org.junit.Assert.*;

public class PressureEngineTest {

    private static Clock scripted(double... seq) {
        AtomicInteger idx = new AtomicInteger(0);
        return () -> {
            int i = idx.getAndIncrement();
            return i < seq.length ? seq[i] : seq[seq.length - 1];
        };
    }

    @Test
    public void defaultConfigIsValid() {
        PressureConfig.defaults().validate();
    }

    @Test
    public void rejectsReleaseBelowEscalation() {
        PressureConfig cfg = PressureConfig.builder()
            .escalationThreshold(0.9)
            .releaseThreshold(0.5)
            .build();
        try {
            cfg.validate();
            fail("expected ConfigException");
        } catch (ConfigException e) {
            assertTrue(e.getMessage().contains("release_threshold"));
        }
    }

    @Test
    public void rejectsNegativeCoefficient() {
        PressureConfig cfg = PressureConfig.builder().tokenCoefficient(-0.01).build();
        try {
            cfg.validate();
            fail("expected ConfigException");
        } catch (ConfigException e) {
            assertTrue(e.getMessage().contains("token_coefficient"));
        }
    }

    @Test
    public void stepAccumulatesPressure() {
        PressureConfig cfg = PressureConfig.builder().dissipationPerStep(0.0).build();
        Clock clk = scripted(0.0, 0.1, 0.2);
        MemorySink sink = new MemorySink();
        PressureEngine engine = new PressureEngine(cfg,
            EngineOptions.builder().executionId("t").auditSink(sink).clock(clk).timestampClock(clk).build());

        StepOutcome out = engine.step(StepInput.builder().tokens(1000).build());
        assertEquals(StepOutcome.OK, out);
        assertEquals(0.015, engine.getPressure(), 1e-9);
    }

    @Test
    public void stepEscalatesAtThreshold() {
        PressureConfig cfg = PressureConfig.builder()
            .escalationThreshold(0.5)
            .releaseThreshold(0.95)
            .dissipationPerStep(0.0)
            .depthCoefficient(0.6)
            .build();
        Clock clk = scripted(0.0, 0.1);
        PressureEngine engine = new PressureEngine(cfg,
            EngineOptions.builder().executionId("t").clock(clk).timestampClock(clk).build());

        StepOutcome out = engine.step(StepInput.builder().depth(1).build());
        assertEquals(StepOutcome.ESCALATED, out);
        assertEquals(Lifecycle.ESCALATED, engine.getLifecycle());
    }

    @Test
    public void stepReleasesAndLocks() {
        PressureConfig cfg = PressureConfig.builder()
            .escalationThreshold(0.5)
            .releaseThreshold(0.75)
            .dissipationPerStep(0.0)
            .depthCoefficient(0.8)
            .postReleaseLock(true)
            .build();
        Clock clk = scripted(0.0, 0.1);
        PressureEngine engine = new PressureEngine(cfg,
            EngineOptions.builder().executionId("t").clock(clk).timestampClock(clk).build());

        StepOutcome out = engine.step(StepInput.builder().depth(1).build());
        assertEquals(StepOutcome.RELEASED, out);
        assertEquals(Lifecycle.LOCKED, engine.getLifecycle());
        assertEquals(0.0, engine.getPressure(), 0.0);
    }

    @Test
    public void lockedRejectsSubsequentSteps() {
        PressureConfig cfg = PressureConfig.builder()
            .escalationThreshold(0.5)
            .releaseThreshold(0.75)
            .dissipationPerStep(0.0)
            .depthCoefficient(0.8)
            .build();
        Clock clk = scripted(0.0, 0.1, 0.2);
        MemorySink sink = new MemorySink();
        PressureEngine engine = new PressureEngine(cfg,
            EngineOptions.builder().executionId("t").auditSink(sink).clock(clk).timestampClock(clk).build());

        engine.step(StepInput.builder().depth(1).build());
        StepOutcome out = engine.step(StepInput.builder().tokens(100).build());
        assertEquals(StepOutcome.LOCKED, out);

        boolean sawRejected = false;
        for (Event e : sink.events()) {
            if ("engine.step.rejected".equals(e.getKind())) {
                sawRejected = true;
            }
        }
        assertTrue("expected engine.step.rejected event", sawRejected);
    }

    @Test
    public void resetClearsState() {
        PressureConfig cfg = PressureConfig.builder()
            .escalationThreshold(0.5)
            .releaseThreshold(0.75)
            .dissipationPerStep(0.0)
            .depthCoefficient(0.8)
            .build();
        Clock clk = scripted(0.0, 0.1, 0.2);
        PressureEngine engine = new PressureEngine(cfg,
            EngineOptions.builder().executionId("t").clock(clk).timestampClock(clk).build());

        engine.step(StepInput.builder().depth(1).build());
        engine.reset();
        assertEquals(0.0, engine.getPressure(), 0.0);
        assertEquals(Lifecycle.INIT, engine.getLifecycle());
    }

    @Test
    public void clampsPressureAtOne() {
        PressureConfig cfg = PressureConfig.builder()
            .escalationThreshold(0.5)
            .releaseThreshold(0.99)
            .dissipationPerStep(0.0)
            .postReleaseLock(false)
            .depthCoefficient(5.0)
            .build();
        Clock clk = scripted(0.0, 0.1);
        PressureEngine engine = new PressureEngine(cfg,
            EngineOptions.builder().executionId("t").clock(clk).timestampClock(clk).build());

        engine.step(StepInput.builder().depth(1).build());
        assertTrue("pressure should be clamped <= 1.0",
            engine.getPressure() <= 1.0 + 1e-9);
    }

    @Test
    public void lifecycleWireValuesMatchSpec() {
        assertEquals("init", Lifecycle.INIT.toString());
        assertEquals("running", Lifecycle.RUNNING.toString());
        assertEquals("escalated", Lifecycle.ESCALATED.toString());
        assertEquals("released", Lifecycle.RELEASED.toString());
        assertEquals("locked", Lifecycle.LOCKED.toString());
    }
}
