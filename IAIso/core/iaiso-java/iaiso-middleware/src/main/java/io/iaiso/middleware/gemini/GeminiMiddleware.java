package io.iaiso.middleware.gemini;

import com.google.gson.JsonObject;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.StepInput;
import io.iaiso.core.StepOutcome;
import io.iaiso.middleware.MiddlewareException;

import java.util.ArrayList;
import java.util.List;

/** IAIso wrapper for Google Gemini / Vertex AI generative models. */
public final class GeminiMiddleware {
    private GeminiMiddleware() {}

    public interface Model {
        Response generateContent(JsonObject request);
        String modelName();
    }

    public static final class UsageMetadata {
        public long promptTokenCount;
        public long candidatesTokenCount;
        public long totalTokenCount;
    }

    public static final class Part {
        public final boolean hasFunctionCall;
        public Part(boolean hasFunctionCall) { this.hasFunctionCall = hasFunctionCall; }
    }

    public static final class Candidate {
        public final List<Part> parts;
        public Candidate(List<Part> parts) {
            this.parts = parts != null ? parts : new ArrayList<>();
        }
    }

    public static final class Response {
        public final UsageMetadata usageMetadata;
        public final List<Candidate> candidates;
        public Response(UsageMetadata um, List<Candidate> candidates) {
            this.usageMetadata = um != null ? um : new UsageMetadata();
            this.candidates = candidates != null ? candidates : new ArrayList<>();
        }
    }

    public static final class Options {
        public final boolean raiseOnEscalation;
        public Options(boolean raiseOnEscalation) { this.raiseOnEscalation = raiseOnEscalation; }
        public static Options defaults() { return new Options(false); }
    }

    public static final class BoundedModel {
        private final Model raw;
        private final BoundedExecution execution;
        private final Options opts;

        public BoundedModel(Model raw, BoundedExecution execution, Options opts) {
            this.raw = raw; this.execution = execution;
            this.opts = opts != null ? opts : Options.defaults();
        }

        public Response generateContent(JsonObject request) {
            StepOutcome pre = execution.check();
            if (pre == StepOutcome.LOCKED) throw new MiddlewareException.Locked();
            if (pre == StepOutcome.ESCALATED && opts.raiseOnEscalation) {
                throw new MiddlewareException.EscalationRaised();
            }
            Response resp;
            try {
                resp = raw.generateContent(request);
            } catch (RuntimeException e) {
                throw new MiddlewareException.Provider(e.getMessage(), e);
            }
            long tokens = resp.usageMetadata.totalTokenCount;
            if (tokens == 0) {
                tokens = resp.usageMetadata.promptTokenCount + resp.usageMetadata.candidatesTokenCount;
            }
            long toolCalls = 0;
            for (Candidate c : resp.candidates) {
                for (Part p : c.parts) if (p.hasFunctionCall) toolCalls++;
            }
            String model = raw.modelName() != null && !raw.modelName().isEmpty()
                ? raw.modelName() : "unknown";
            execution.recordStep(StepInput.builder()
                .tokens(tokens).toolCalls(toolCalls)
                .tag("gemini.generateContent:" + model)
                .build());
            return resp;
        }
    }
}
