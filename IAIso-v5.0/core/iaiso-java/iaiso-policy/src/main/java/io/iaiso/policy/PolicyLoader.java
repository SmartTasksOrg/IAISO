package io.iaiso.policy;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.iaiso.core.ConfigException;
import io.iaiso.core.PressureConfig;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Pattern;

/**
 * IAIso policy loader. JSON only — Java has no built-in YAML support
 * and the Java port intentionally avoids extra dependencies. Convert
 * YAML policies to JSON outside this SDK if needed.
 */
public final class PolicyLoader {

    private static final Pattern SCOPE_PATTERN =
        Pattern.compile("^[a-z0-9_-]+(\\.[a-z0-9_-]+)*$");

    private PolicyLoader() {}

    /** Validate a parsed JSON document against {@code spec/policy/README.md}. */
    public static void validate(JsonElement doc) {
        if (doc == null || !doc.isJsonObject()) {
            throw new PolicyException("$: policy document must be a mapping");
        }
        JsonObject root = doc.getAsJsonObject();
        if (!root.has("version")) {
            throw new PolicyException("$: required property 'version' missing");
        }
        JsonElement v = root.get("version");
        if (!v.isJsonPrimitive() || !v.getAsJsonPrimitive().isString()
                || !"1".equals(v.getAsString())) {
            throw new PolicyException("$.version: must be exactly \"1\", got " + v);
        }

        if (root.has("pressure")) {
            JsonElement pressure = root.get("pressure");
            if (!pressure.isJsonObject()) {
                throw new PolicyException("$.pressure: must be a mapping");
            }
            JsonObject pObj = pressure.getAsJsonObject();
            String[] nonNeg = {
                "token_coefficient", "tool_coefficient", "depth_coefficient",
                "dissipation_per_step", "dissipation_per_second"
            };
            for (String f : nonNeg) {
                if (pObj.has(f)) {
                    Double n = numeric(pObj.get(f));
                    if (n == null) {
                        throw new PolicyException("$.pressure." + f + ": expected number");
                    }
                    if (n < 0) {
                        throw new PolicyException(
                            "$.pressure." + f + ": must be non-negative (got " + n + ")");
                    }
                }
            }
            String[] thresholds = {"escalation_threshold", "release_threshold"};
            for (String f : thresholds) {
                if (pObj.has(f)) {
                    Double n = numeric(pObj.get(f));
                    if (n == null) {
                        throw new PolicyException("$.pressure." + f + ": expected number");
                    }
                    if (n < 0 || n > 1) {
                        throw new PolicyException(
                            "$.pressure." + f + ": must be in [0, 1] (got " + n + ")");
                    }
                }
            }
            if (pObj.has("post_release_lock")
                    && !(pObj.get("post_release_lock").isJsonPrimitive()
                        && pObj.get("post_release_lock").getAsJsonPrimitive().isBoolean())) {
                throw new PolicyException(
                    "$.pressure.post_release_lock: expected boolean");
            }
            // Cross-field
            Double esc = pObj.has("escalation_threshold")
                ? numeric(pObj.get("escalation_threshold")) : null;
            Double rel = pObj.has("release_threshold")
                ? numeric(pObj.get("release_threshold")) : null;
            if (esc != null && rel != null && rel <= esc) {
                throw new PolicyException(
                    "$.pressure.release_threshold: must exceed escalation_threshold ("
                    + rel + " <= " + esc + ")");
            }
        }

        if (root.has("coordinator")) {
            JsonElement coord = root.get("coordinator");
            if (!coord.isJsonObject()) {
                throw new PolicyException("$.coordinator: must be a mapping");
            }
            JsonObject cObj = coord.getAsJsonObject();
            if (cObj.has("aggregator")) {
                String name = cObj.get("aggregator").getAsString();
                if (!"sum".equals(name) && !"mean".equals(name)
                        && !"max".equals(name) && !"weighted_sum".equals(name)) {
                    throw new PolicyException(
                        "$.coordinator.aggregator: must be one of sum|mean|max|weighted_sum (got "
                        + name + ")");
                }
            }
            Double esc = cObj.has("escalation_threshold")
                ? numeric(cObj.get("escalation_threshold")) : null;
            Double rel = cObj.has("release_threshold")
                ? numeric(cObj.get("release_threshold")) : null;
            if (esc != null && rel != null && rel <= esc) {
                throw new PolicyException(
                    "$.coordinator.release_threshold: must exceed escalation_threshold ("
                    + rel + " <= " + esc + ")");
            }
        }

        if (root.has("consent")) {
            JsonElement consent = root.get("consent");
            if (!consent.isJsonObject()) {
                throw new PolicyException("$.consent: must be a mapping");
            }
            JsonObject cObj = consent.getAsJsonObject();
            if (cObj.has("required_scopes")) {
                JsonElement scopes = cObj.get("required_scopes");
                if (!scopes.isJsonArray()) {
                    throw new PolicyException("$.consent.required_scopes: expected list");
                }
                JsonArray arr = scopes.getAsJsonArray();
                for (int i = 0; i < arr.size(); i++) {
                    String s = arr.get(i).getAsString();
                    if (!SCOPE_PATTERN.matcher(s).matches()) {
                        throw new PolicyException(
                            "$.consent.required_scopes[" + i + "]: " + s + " is not a valid scope");
                    }
                }
            }
        }
    }

    /** Build a {@link Policy} from a parsed JSON document. */
    public static Policy build(JsonElement doc) {
        validate(doc);
        JsonObject root = doc.getAsJsonObject();

        PressureConfig.Builder pcb = PressureConfig.builder();
        if (root.has("pressure") && root.get("pressure").isJsonObject()) {
            JsonObject p = root.getAsJsonObject("pressure");
            applyDouble(p, "escalation_threshold", pcb::escalationThreshold);
            applyDouble(p, "release_threshold", pcb::releaseThreshold);
            applyDouble(p, "dissipation_per_step", pcb::dissipationPerStep);
            applyDouble(p, "dissipation_per_second", pcb::dissipationPerSecond);
            applyDouble(p, "token_coefficient", pcb::tokenCoefficient);
            applyDouble(p, "tool_coefficient", pcb::toolCoefficient);
            applyDouble(p, "depth_coefficient", pcb::depthCoefficient);
            if (p.has("post_release_lock")) {
                pcb.postReleaseLock(p.get("post_release_lock").getAsBoolean());
            }
        }
        PressureConfig pressure = pcb.build();
        try {
            pressure.validate();
        } catch (ConfigException e) {
            throw new PolicyException("$.pressure: " + e.getMessage(), e);
        }

        CoordinatorConfig coord = CoordinatorConfig.defaults();
        Aggregator aggregator = new SumAggregator();
        if (root.has("coordinator") && root.get("coordinator").isJsonObject()) {
            JsonObject c = root.getAsJsonObject("coordinator");
            double escThr = c.has("escalation_threshold")
                ? numericNonNull(c.get("escalation_threshold"), coord.getEscalationThreshold())
                : coord.getEscalationThreshold();
            double relThr = c.has("release_threshold")
                ? numericNonNull(c.get("release_threshold"), coord.getReleaseThreshold())
                : coord.getReleaseThreshold();
            double cooldown = c.has("notify_cooldown_seconds")
                ? numericNonNull(c.get("notify_cooldown_seconds"), coord.getNotifyCooldownSeconds())
                : coord.getNotifyCooldownSeconds();
            coord = new CoordinatorConfig(escThr, relThr, cooldown);
            aggregator = buildAggregator(c);
        }

        ConsentPolicy consent = ConsentPolicy.defaults();
        if (root.has("consent") && root.get("consent").isJsonObject()) {
            JsonObject c = root.getAsJsonObject("consent");
            String issuer = c.has("issuer") ? c.get("issuer").getAsString() : null;
            double ttl = c.has("default_ttl_seconds")
                ? numericNonNull(c.get("default_ttl_seconds"), consent.getDefaultTtlSeconds())
                : consent.getDefaultTtlSeconds();
            List<String> required = consent.getRequiredScopes();
            if (c.has("required_scopes")) {
                List<String> tmp = new ArrayList<>();
                for (JsonElement el : c.getAsJsonArray("required_scopes")) {
                    tmp.add(el.getAsString());
                }
                required = tmp;
            }
            List<String> algos = consent.getAllowedAlgorithms();
            if (c.has("allowed_algorithms")) {
                List<String> tmp = new ArrayList<>();
                for (JsonElement el : c.getAsJsonArray("allowed_algorithms")) {
                    tmp.add(el.getAsString());
                }
                algos = tmp;
            }
            consent = new ConsentPolicy(issuer, ttl, required, algos);
        }

        JsonObject metadata = root.has("metadata") && root.get("metadata").isJsonObject()
            ? root.getAsJsonObject("metadata")
            : new JsonObject();

        return new Policy("1", pressure, coord, consent, aggregator, metadata);
    }

    /** Parse JSON-encoded policy bytes. */
    public static Policy parseJson(byte[] data) {
        try {
            JsonElement doc = JsonParser.parseString(new String(data, StandardCharsets.UTF_8));
            return build(doc);
        } catch (PolicyException e) {
            throw e;
        } catch (Exception e) {
            throw new PolicyException("policy JSON parse failed: " + e.getMessage(), e);
        }
    }

    /** Load a policy from a file (.json only). */
    public static Policy load(Path path) {
        try {
            byte[] data = Files.readAllBytes(path);
            String name = path.toString().toLowerCase();
            if (name.endsWith(".json")) {
                return parseJson(data);
            }
            throw new PolicyException(
                "unsupported policy file extension: " + path
                + " (only .json is supported in the Java SDK)");
        } catch (IOException e) {
            throw new PolicyException("failed to read " + path + ": " + e.getMessage(), e);
        }
    }

    private static Aggregator buildAggregator(JsonObject coord) {
        String name = coord.has("aggregator")
            ? coord.get("aggregator").getAsString() : "sum";
        switch (name) {
            case "mean": return new MeanAggregator();
            case "max": return new MaxAggregator();
            case "weighted_sum":
                Map<String, Double> weights = new HashMap<>();
                if (coord.has("weights") && coord.get("weights").isJsonObject()) {
                    for (Map.Entry<String, JsonElement> e
                            : coord.getAsJsonObject("weights").entrySet()) {
                        Double v = numeric(e.getValue());
                        if (v != null) weights.put(e.getKey(), v);
                    }
                }
                double dw = coord.has("default_weight")
                    ? numericNonNull(coord.get("default_weight"), 1.0) : 1.0;
                return new WeightedSumAggregator(weights, dw);
            default: return new SumAggregator();
        }
    }

    private static Double numeric(JsonElement e) {
        if (e == null || !e.isJsonPrimitive()) return null;
        // Reject strings that happen to parse as numbers — the spec's
        // wrong_type vectors require strict type checking.
        if (!e.getAsJsonPrimitive().isNumber()) return null;
        try {
            return e.getAsDouble();
        } catch (Exception ex) {
            return null;
        }
    }

    private static double numericNonNull(JsonElement e, double fallback) {
        Double d = numeric(e);
        return d != null ? d : fallback;
    }

    @FunctionalInterface
    private interface DoubleSetter {
        void set(double v);
    }

    private static void applyDouble(JsonObject obj, String key, DoubleSetter setter) {
        if (obj.has(key)) {
            Double v = numeric(obj.get(key));
            if (v != null) setter.set(v);
        }
    }
}
