package io.iaiso.middleware.mistral;

import com.google.gson.JsonObject;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.StepInput;
import io.iaiso.core.StepOutcome;
import io.iaiso.middleware.MiddlewareException;

import java.util.ArrayList;
import java.util.List;

/** IAIso wrapper for Mistral chat. */
public final class MistralMiddleware {
    private MistralMiddleware() {}

    public interface Client {
        Response chatComplete(JsonObject params);
    }

    public static final class Usage {
        public long promptTokens;
        public long completionTokens;
        public long totalTokens;
    }

    public static final class Choice {
        public final List<String> toolCalls;
        public Choice(List<String> toolCalls) {
            this.toolCalls = toolCalls != null ? toolCalls : new ArrayList<>();
        }
    }

    public static final class Response {
        public final String model;
        public final Usage usage;
        public final List<Choice> choices;
        public Response(String model, Usage usage, List<Choice> choices) {
            this.model = model;
            this.usage = usage != null ? usage : new Usage();
            this.choices = choices != null ? choices : new ArrayList<>();
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

        public Response chatComplete(JsonObject params) {
            StepOutcome pre = execution.check();
            if (pre == StepOutcome.LOCKED) throw new MiddlewareException.Locked();
            if (pre == StepOutcome.ESCALATED && opts.raiseOnEscalation) {
                throw new MiddlewareException.EscalationRaised();
            }
            Response resp;
            try {
                resp = raw.chatComplete(params);
            } catch (RuntimeException e) {
                throw new MiddlewareException.Provider(e.getMessage(), e);
            }
            long tokens = resp.usage.totalTokens;
            if (tokens == 0) tokens = resp.usage.promptTokens + resp.usage.completionTokens;
            long toolCalls = 0;
            for (Choice c : resp.choices) toolCalls += c.toolCalls.size();
            String model = (resp.model == null || resp.model.isEmpty()) ? "unknown" : resp.model;
            execution.recordStep(StepInput.builder()
                .tokens(tokens).toolCalls(toolCalls)
                .tag("mistral.chat.complete:" + model)
                .build());
            return resp;
        }
    }
}
