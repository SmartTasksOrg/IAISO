package io.iaiso.conformance;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import io.iaiso.policy.Policy;
import io.iaiso.policy.PolicyException;
import io.iaiso.policy.PolicyLoader;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.List;

final class PolicyRunner {
    static final double TOLERANCE = 1e-9;

    private PolicyRunner() {}

    static List<VectorResult> run(Path specRoot) throws IOException {
        Path file = specRoot.resolve("policy").resolve("vectors.json");
        JsonObject doc = JsonParser.parseString(
            new String(Files.readAllBytes(file))).getAsJsonObject();
        List<VectorResult> out = new ArrayList<>();
        if (doc.has("valid")) {
            for (JsonElement el : doc.getAsJsonArray("valid")) {
                out.add(runValid(el.getAsJsonObject()));
            }
        }
        if (doc.has("invalid")) {
            for (JsonElement el : doc.getAsJsonArray("invalid")) {
                out.add(runInvalid(el.getAsJsonObject()));
            }
        }
        return out;
    }

    private static VectorResult runValid(JsonObject v) {
        String name = "valid/" + v.get("name").getAsString();
        try {
            Policy p = PolicyLoader.build(v.get("document"));

            if (v.has("expected_pressure") && v.get("expected_pressure").isJsonObject()) {
                JsonObject ep = v.getAsJsonObject("expected_pressure");
                String err = checkPressure(p, ep);
                if (err != null) return VectorResult.fail("policy", name, err);
            }

            if (v.has("expected_consent") && v.get("expected_consent").isJsonObject()) {
                JsonObject ec = v.getAsJsonObject("expected_consent");
                String err = checkConsent(p, ec);
                if (err != null) return VectorResult.fail("policy", name, err);
            }

            if (v.has("expected_metadata") && v.get("expected_metadata").isJsonObject()) {
                JsonObject em = v.getAsJsonObject("expected_metadata");
                if (em.size() != p.getMetadata().size()) {
                    return VectorResult.fail("policy", name,
                        "metadata size: got " + p.getMetadata().size()
                        + ", want " + em.size());
                }
            }

            return VectorResult.pass("policy", name);
        } catch (RuntimeException e) {
            return VectorResult.fail("policy", name, "build failed: " + e.getMessage());
        }
    }

    private static String checkPressure(Policy p, JsonObject ep) {
        double[][] checks = {
            {p.getPressure().getTokenCoefficient(),
                ep.has("token_coefficient") ? ep.get("token_coefficient").getAsDouble() : Double.NaN},
            {p.getPressure().getToolCoefficient(),
                ep.has("tool_coefficient") ? ep.get("tool_coefficient").getAsDouble() : Double.NaN},
            {p.getPressure().getDepthCoefficient(),
                ep.has("depth_coefficient") ? ep.get("depth_coefficient").getAsDouble() : Double.NaN},
            {p.getPressure().getDissipationPerStep(),
                ep.has("dissipation_per_step") ? ep.get("dissipation_per_step").getAsDouble() : Double.NaN},
            {p.getPressure().getDissipationPerSecond(),
                ep.has("dissipation_per_second") ? ep.get("dissipation_per_second").getAsDouble() : Double.NaN},
            {p.getPressure().getEscalationThreshold(),
                ep.has("escalation_threshold") ? ep.get("escalation_threshold").getAsDouble() : Double.NaN},
            {p.getPressure().getReleaseThreshold(),
                ep.has("release_threshold") ? ep.get("release_threshold").getAsDouble() : Double.NaN},
        };
        String[] labels = {
            "token_coefficient", "tool_coefficient", "depth_coefficient",
            "dissipation_per_step", "dissipation_per_second",
            "escalation_threshold", "release_threshold"
        };
        for (int i = 0; i < checks.length; i++) {
            if (Double.isNaN(checks[i][1])) continue;
            if (Math.abs(checks[i][0] - checks[i][1]) > TOLERANCE) {
                return labels[i] + ": got " + checks[i][0] + ", want " + checks[i][1];
            }
        }
        if (ep.has("post_release_lock")) {
            boolean want = ep.get("post_release_lock").getAsBoolean();
            if (want != p.getPressure().isPostReleaseLock()) {
                return "post_release_lock mismatch";
            }
        }
        return null;
    }

    private static String checkConsent(Policy p, JsonObject ec) {
        if (ec.has("issuer")) {
            String want = ec.get("issuer").isJsonNull() ? null : ec.get("issuer").getAsString();
            String got = p.getConsent().getIssuer();
            if (want == null ? got != null : !want.equals(got)) {
                return "consent.issuer: got " + got + ", want " + want;
            }
        }
        if (ec.has("default_ttl_seconds")) {
            double want = ec.get("default_ttl_seconds").getAsDouble();
            if (Math.abs(p.getConsent().getDefaultTtlSeconds() - want) > TOLERANCE) {
                return "default_ttl_seconds: got " + p.getConsent().getDefaultTtlSeconds()
                    + ", want " + want;
            }
        }
        if (ec.has("required_scopes")) {
            JsonArray want = ec.getAsJsonArray("required_scopes");
            if (want.size() != p.getConsent().getRequiredScopes().size()) {
                return "required_scopes length mismatch";
            }
        }
        if (ec.has("allowed_algorithms")) {
            JsonArray want = ec.getAsJsonArray("allowed_algorithms");
            if (want.size() != p.getConsent().getAllowedAlgorithms().size()) {
                return "allowed_algorithms length mismatch";
            }
        }
        return null;
    }

    private static VectorResult runInvalid(JsonObject v) {
        String name = "invalid/" + v.get("name").getAsString();
        String expectPath = v.get("expect_error_path").getAsString();
        try {
            // For non-mapping documents we still need to call build()
            JsonElement doc = v.get("document");
            PolicyLoader.build(doc);
            return VectorResult.fail("policy", name,
                "expected error containing '" + expectPath + "', got Ok");
        } catch (PolicyException e) {
            if (!e.getMessage().contains(expectPath)) {
                return VectorResult.fail("policy", name,
                    "expected error containing '" + expectPath + "', got: " + e.getMessage());
            }
            return VectorResult.pass("policy", name);
        }
    }
}
