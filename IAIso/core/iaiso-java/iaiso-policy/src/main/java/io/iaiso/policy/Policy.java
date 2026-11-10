package io.iaiso.policy;

import com.google.gson.JsonObject;
import io.iaiso.core.PressureConfig;

/** Assembled, validated policy document. */
public final class Policy {
    private final String version;
    private final PressureConfig pressure;
    private final CoordinatorConfig coordinator;
    private final ConsentPolicy consent;
    private final Aggregator aggregator;
    private final JsonObject metadata;

    public Policy(String version, PressureConfig pressure, CoordinatorConfig coordinator,
                  ConsentPolicy consent, Aggregator aggregator, JsonObject metadata) {
        this.version = version;
        this.pressure = pressure;
        this.coordinator = coordinator;
        this.consent = consent;
        this.aggregator = aggregator;
        this.metadata = metadata != null ? metadata : new JsonObject();
    }

    public String getVersion() { return version; }
    public PressureConfig getPressure() { return pressure; }
    public CoordinatorConfig getCoordinator() { return coordinator; }
    public ConsentPolicy getConsent() { return consent; }
    public Aggregator getAggregator() { return aggregator; }
    public JsonObject getMetadata() { return metadata; }
}
