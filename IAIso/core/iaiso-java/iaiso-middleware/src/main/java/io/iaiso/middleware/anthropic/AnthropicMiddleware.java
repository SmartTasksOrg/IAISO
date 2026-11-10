package io.iaiso.middleware.anthropic;

import com.google.gson.JsonObject;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.StepInput;
import io.iaiso.core.StepOutcome;
import io.iaiso.middleware.MiddlewareException;

import java.util.ArrayList;
import java.util.List;

/**
 * IAIso wrapper for Anthropic's Messages API.
 *
 * <p>Implement {@link Client} around your favorite Anthropic SDK
 * (anthropic-java, anthropic-bedrock, etc.) to plug it in.
 */
public final class AnthropicMiddleware {

    private AnthropicMiddleware() {}

    /** Structural client interface — one method per Anthropic operation. */
    public interface Client {
        Response messagesCreate(JsonObject params);
    }

    /** Anthropic response — minimal subset of fields we need. */
    public static final class Response {
        public final String model;
        public final long inputTokens;
        public final long outputTokens;
        public final List<ContentBlock> content;

        public Response(String model, long inputTokens, long outputTokens, List<ContentBlock> content) {
            this.model = model;
            this.inputTokens = inputTokens;
            this.outputTokens = outputTokens;
            this.content = content != null ? content : new ArrayList<>();
        }
    }

    /** A content block in a response. */
    public static final class ContentBlock {
        public final String type;
        public ContentBlock(String type) { this.type = type; }
    }

    /** Options for {@link BoundedClient}. */
    public static final class Options {
        public final boolean raiseOnEscalation;
        public Options(boolean raiseOnEscalation) {
            this.raiseOnEscalation = raiseOnEscalation;
        }
        public static Options defaults() { return new Options(false); }
    }

    /** Wraps a {@link Client} so every call is accounted against a {@link BoundedExecution}. */
    public static final class BoundedClient {
        private final Client raw;
        private final BoundedExecution execution;
        private final Options opts;

        public BoundedClient(Client raw, BoundedExecution execution, Options opts) {
            this.raw = raw;
            this.execution = execution;
            this.opts = opts != null ? opts : Options.defaults();
        }

        public Response messagesCreate(JsonObject params) {
            StepOutcome pre = execution.check();
            if (pre == StepOutcome.LOCKED) throw new MiddlewareException.Locked();
            if (pre == StepOutcome.ESCALATED && opts.raiseOnEscalation) {
                throw new MiddlewareException.EscalationRaised();
            }
            Response resp;
            try {
                resp = raw.messagesCreate(params);
            } catch (RuntimeException e) {
                throw new MiddlewareException.Provider(e.getMessage(), e);
            }
            long tokens = resp.inputTokens + resp.outputTokens;
            long toolCalls = 0;
            for (ContentBlock b : resp.content) {
                if ("tool_use".equals(b.type)) toolCalls++;
            }
            String model = (resp.model == null || resp.model.isEmpty()) ? "unknown" : resp.model;
            execution.recordStep(StepInput.builder()
                .tokens(tokens)
                .toolCalls(toolCalls)
                .tag("anthropic.messages.create:" + model)
                .build());
            return resp;
        }
    }
}
