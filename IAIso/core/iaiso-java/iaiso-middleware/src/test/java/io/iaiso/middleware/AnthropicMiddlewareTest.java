package io.iaiso.middleware;

import com.google.gson.JsonObject;
import io.iaiso.audit.MemorySink;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.BoundedExecutionOptions;
import io.iaiso.core.PressureConfig;
import io.iaiso.core.StepInput;
import io.iaiso.middleware.anthropic.AnthropicMiddleware;
import org.junit.Test;

import java.util.Arrays;

import static org.junit.Assert.*;

public class AnthropicMiddlewareTest {

    @Test
    public void accountsTokensAndToolCalls() {
        MemorySink sink = new MemorySink();
        BoundedExecution exec = BoundedExecution.start(BoundedExecutionOptions.builder()
            .auditSink(sink).build());

        AnthropicMiddleware.Client raw = params -> new AnthropicMiddleware.Response(
            "claude-opus-4-7", 100L, 250L,
            Arrays.asList(
                new AnthropicMiddleware.ContentBlock("text"),
                new AnthropicMiddleware.ContentBlock("tool_use"),
                new AnthropicMiddleware.ContentBlock("tool_use")
            ));
        AnthropicMiddleware.BoundedClient client = new AnthropicMiddleware.BoundedClient(
            raw, exec, AnthropicMiddleware.Options.defaults());
        client.messagesCreate(new JsonObject());

        boolean foundStep = false;
        for (var e : sink.events()) {
            if ("engine.step".equals(e.getKind())) {
                assertEquals(350L, ((Number) e.getData().get("tokens")).longValue());
                assertEquals(2L, ((Number) e.getData().get("tool_calls")).longValue());
                foundStep = true;
            }
        }
        assertTrue("expected engine.step event", foundStep);
        exec.close();
    }

    @Test
    public void raisesOnEscalationWhenOptedIn() {
        PressureConfig cfg = PressureConfig.builder()
            .escalationThreshold(0.4)
            .releaseThreshold(0.95)
            .depthCoefficient(0.5)
            .dissipationPerStep(0.0)
            .build();
        BoundedExecution exec = BoundedExecution.start(BoundedExecutionOptions.builder()
            .config(cfg).build());
        // Force escalation
        exec.recordStep(StepInput.builder().depth(1).build());

        AnthropicMiddleware.Client raw = params ->
            new AnthropicMiddleware.Response("model", 0, 0, java.util.Collections.emptyList());
        AnthropicMiddleware.BoundedClient client = new AnthropicMiddleware.BoundedClient(
            raw, exec, new AnthropicMiddleware.Options(true));
        try {
            client.messagesCreate(new JsonObject());
            fail("expected EscalationRaised");
        } catch (MiddlewareException.EscalationRaised expected) {}
        exec.close();
    }
}
