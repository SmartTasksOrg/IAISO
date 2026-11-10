package io.iaiso.audit;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;

import java.util.Collections;
import java.util.Map;
import java.util.TreeMap;

/**
 * A canonical IAIso audit event.
 *
 * <p>The JSON serialization writes fields in the spec-mandated order:
 * {@code schema_version, execution_id, kind, timestamp, data}. The
 * {@code data} map's keys are sorted alphabetically (via {@link TreeMap})
 * so identical inputs produce byte-identical output across runs and
 * across all reference SDKs.
 */
public final class Event {

    /** Current audit envelope schema version. */
    public static final String SCHEMA_VERSION = "1.0";

    private static final Gson GSON =
        new GsonBuilder().disableHtmlEscaping().serializeNulls().create();

    private final String schemaVersion;
    private final String executionId;
    private final String kind;
    private final double timestamp;
    private final Map<String, Object> data;

    /** Construct an Event with the current SCHEMA_VERSION. */
    public Event(String executionId, String kind, double timestamp, Map<String, Object> data) {
        this.schemaVersion = SCHEMA_VERSION;
        this.executionId = executionId;
        this.kind = kind;
        this.timestamp = timestamp;
        this.data = data == null
            ? Collections.emptyMap()
            : Collections.unmodifiableMap(new TreeMap<>(data));
    }

    public String getSchemaVersion() { return schemaVersion; }
    public String getExecutionId() { return executionId; }
    public String getKind() { return kind; }
    public double getTimestamp() { return timestamp; }
    public Map<String, Object> getData() { return data; }

    /**
     * Serialize to JSON in the spec-mandated key order.
     * <p>
     * Hand-built to guarantee key ordering — the key order in the output
     * is {@code schema_version, execution_id, kind, timestamp, data},
     * regardless of how Gson would otherwise serialize the fields.
     */
    public String toJson() {
        StringBuilder sb = new StringBuilder();
        sb.append('{');
        sb.append("\"schema_version\":").append(GSON.toJson(schemaVersion));
        sb.append(",\"execution_id\":").append(GSON.toJson(executionId));
        sb.append(",\"kind\":").append(GSON.toJson(kind));
        sb.append(",\"timestamp\":").append(formatNumber(timestamp));
        sb.append(",\"data\":").append(GSON.toJson(data));
        sb.append('}');
        return sb.toString();
    }

    /**
     * Format a double the way the other reference SDKs do:
     * integers as {@code 0}, {@code 1700000000} (no trailing decimals),
     * non-integers with their natural representation.
     */
    private static String formatNumber(double d) {
        if (d == Math.floor(d) && !Double.isInfinite(d)) {
            long asLong = (long) d;
            if ((double) asLong == d) {
                return Long.toString(asLong);
            }
        }
        return Double.toString(d);
    }

    @Override
    public String toString() {
        return toJson();
    }
}
