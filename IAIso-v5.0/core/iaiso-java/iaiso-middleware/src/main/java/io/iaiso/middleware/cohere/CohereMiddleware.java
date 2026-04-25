package io.iaiso.middleware.cohere;

import com.google.gson.JsonObject;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.StepInput;
import io.iaiso.core.StepOutcome;
import io.iaiso.middleware.MiddlewareException;

import java.util.ArrayList;
import java.util.List;

/** IAIso wrapper for Cohere chat. */
public final class CohereMiddleware {
    private CohereMiddleware() {}

    public interface Client {
        Response chat(JsonObject params);
    }

    public static final class BilledUnits {
        public long inputTokens;
        public long outputTokens;
    }

    public static final class Meta {
        public BilledUnits tokens;       // either of these may be set
        public BilledUnits billedUnits;  // depending on response shape
    }

    public static final class ToolCall {
        public final String name;
        public ToolCall(String name) { this.name = name; }
    }

    public static final class Response {
        public final String model;
        public final Meta meta;
        public final List<ToolCall> toolCalls;
        public Response(String model, Meta meta, List<ToolCall> toolCalls) {
            this.model = model;
            this.meta = meta != null ? meta : new Meta();
            this.toolCalls = toolCalls != null ? toolCalls : new ArrayList<>();
        }
    }

    public static final class Options {
        public final boolean raiseOnEscalation;
        public Options(boolean raiseOnEscalation) { this.raiseOnEscalation = raiseOnEscalation; }
        public static Options defaults() { return new Options(false); }
    }

    public static final class BoundedClient {
        private final Client raw;
        private final BoundedExecution execution;
        private final Options opts;

        public BoundedClient(Client raw, BoundedExecution execution, Options opts) {
            this.raw = raw; this.execution = execution;
            this.opts = opts != null ? opts : Options.defaults();
        }

        public Response chat(JsonObject params) {
            StepOutcome pre = execution.check();
            if (pre == StepOutcome.LOCKED) throw new MiddlewareException.Locked();
            if (pre == StepOutcome.ESCALATED && opts.raiseOnEscalation) {
                throw new MiddlewareException.EscalationRaised();
            }
            Response resp;
            try {
                resp = raw.chat(params);
            } catch (RuntimeException e) {
                throw new MiddlewareException.Provider(e.getMessage(), e);
            }
            BilledUnits b = resp.meta.tokens != null ? resp.meta.tokens : resp.meta.billedUnits;
            long tokens = b != null ? b.inputTokens + b.outputTokens : 0;
            long toolCalls = resp.toolCalls.size();
            String model = (resp.model == null || resp.model.isEmpty()) ? "unknown" : resp.model;
            execution.recordStep(StepInput.builder()
                .tokens(tokens).toolCalls(toolCalls)
                .tag("cohere.chat:" + model)
                .build());
            return resp;
        }
    }
}
