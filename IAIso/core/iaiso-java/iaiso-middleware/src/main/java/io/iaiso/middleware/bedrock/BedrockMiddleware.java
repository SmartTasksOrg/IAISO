package io.iaiso.middleware.bedrock;

import com.google.gson.JsonObject;
import io.iaiso.core.BoundedExecution;
import io.iaiso.core.StepInput;
import io.iaiso.core.StepOutcome;
import io.iaiso.middleware.MiddlewareException;

import java.util.ArrayList;
import java.util.List;

/**
 * IAIso wrapper for AWS Bedrock runtime. Supports both Converse API
 * (preferred — normalized usage extraction) and the lower-level
 * InvokeModel API.
 */
public final class BedrockMiddleware {
    private BedrockMiddleware() {}

    public interface Client {
        ConverseResponse converse(JsonObject params);
        InvokeResponse invokeModel(JsonObject params);
    }

    public static final class ConverseUsage {
        public long inputTokens;
        public long outputTokens;
        public long totalTokens;
    }

    public static final class ConverseContentBlock {
        public final boolean hasToolUse;
        public ConverseContentBlock(boolean hasToolUse) { this.hasToolUse = hasToolUse; }
    }

    public static final class ConverseResponse {
        public final ConverseUsage usage;
        public final List<ConverseContentBlock> content;
        public ConverseResponse(ConverseUsage usage, List<ConverseContentBlock> content) {
            this.usage = usage != null ? usage : new ConverseUsage();
            this.content = content != null ? content : new ArrayList<>();
        }
    }

    public static final class InvokeResponse {
        public final String modelId;
        public final byte[] body;
        public InvokeResponse(String modelId, byte[] body) {
            this.modelId = modelId;
            this.body = body != null ? body : new byte[0];
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

        public ConverseResponse converse(JsonObject params) {
            checkState();
            ConverseResponse resp;
            try {
                resp = raw.converse(params);
            } catch (RuntimeException e) {
                throw new MiddlewareException.Provider(e.getMessage(), e);
            }
            long tokens = resp.usage.totalTokens;
            if (tokens == 0) tokens = resp.usage.inputTokens + resp.usage.outputTokens;
            long toolCalls = 0;
            for (ConverseContentBlock b : resp.content) {
                if (b.hasToolUse) toolCalls++;
            }
            String modelId = params.has("modelId") ? params.get("modelId").getAsString() : "unknown";
            execution.recordStep(StepInput.builder()
                .tokens(tokens).toolCalls(toolCalls)
                .tag("bedrock.converse:" + modelId)
                .build());
            return resp;
        }

        public InvokeResponse invokeModel(JsonObject params) {
            checkState();
            InvokeResponse resp;
            try {
                resp = raw.invokeModel(params);
            } catch (RuntimeException e) {
                throw new MiddlewareException.Provider(e.getMessage(), e);
            }
            String modelId = (resp.modelId != null && !resp.modelId.isEmpty())
                ? resp.modelId
                : (params.has("modelId") ? params.get("modelId").getAsString() : "unknown");
            // Best-effort: model-specific bodies require the user's adapter
            // to extract token counts. Default to 0; users may add a
            // recordTokens() call with the parsed value if needed.
            execution.recordStep(StepInput.builder()
                .tag("bedrock.invokeModel:" + modelId)
                .build());
            return resp;
        }

        private void checkState() {
            StepOutcome pre = execution.check();
            if (pre == StepOutcome.LOCKED) throw new MiddlewareException.Locked();
            if (pre == StepOutcome.ESCALATED && opts.raiseOnEscalation) {
                throw new MiddlewareException.EscalationRaised();
            }
        }
    }
}
