package io.iaiso.observability;

import io.iaiso.audit.Event;
import io.iaiso.audit.Sink;

import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * IAIso OpenTelemetry tracing sink.
 *
 * <p>Structurally typed against the OTel trace API. The official
 * {@code opentelemetry-java} {@code Tracer} and {@code Span} satisfy
 * these interfaces with thin adapters.
 */
public final class OtelSpanSink implements Sink {

    public interface Span {
        void addEvent(String name, Map<String, Object> attributes);
        void setAttribute(String key, Object value);
        void end();
    }

    public interface Tracer {
        Span startSpan(String name, Map<String, Object> attributes);
    }

    private final Tracer tracer;
    private final String spanName;
    private final ConcurrentHashMap<String, Span> spans = new ConcurrentHashMap<>();

    public OtelSpanSink(Tracer tracer, String spanName) {
        this.tracer = tracer;
        this.spanName = (spanName == null || spanName.isEmpty())
            ? "iaiso.execution" : spanName;
    }

    /** End any open spans. Useful at shutdown. */
    public void closeAll() {
        for (Span s : spans.values()) {
            try { s.end(); } catch (RuntimeException ignored) {}
        }
        spans.clear();
    }

    @Override
    public void emit(Event event) {
        Span span;
        if ("engine.init".equals(event.getKind())) {
            Map<String, Object> attrs = new HashMap<>();
            attrs.put("iaiso.execution_id", event.getExecutionId());
            span = tracer.startSpan(spanName + ":" + event.getExecutionId(), attrs);
            spans.put(event.getExecutionId(), span);
        } else {
            span = spans.get(event.getExecutionId());
        }
        if (span == null) return;

        Map<String, Object> attrs = new HashMap<>(event.getData());
        attrs.put("iaiso.schema_version", event.getSchemaVersion());
        span.addEvent(event.getKind(), attrs);

        switch (event.getKind()) {
            case "engine.step":
                Object p = event.getData().get("pressure");
                if (p != null) span.setAttribute("iaiso.pressure", p);
                break;
            case "engine.escalation":
                span.setAttribute("iaiso.escalated", true);
                break;
            case "engine.release":
                span.setAttribute("iaiso.released", true);
                break;
            case "execution.closed":
                span.end();
                spans.remove(event.getExecutionId());
                break;
            default:
                // ignore
        }
    }
}
