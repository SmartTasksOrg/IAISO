package io.iaiso.cli;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonObject;
import io.iaiso.audit.MemorySink;
import io.iaiso.consent.Algorithm;
import io.iaiso.consent.ConsentException;
import io.iaiso.consent.Issuer;
import io.iaiso.consent.Scope;
import io.iaiso.consent.Verifier;
import io.iaiso.conformance.ConformanceRunner;
import io.iaiso.conformance.SectionResults;
import io.iaiso.conformance.VectorResult;
import io.iaiso.coordination.SharedPressureCoordinator;
import io.iaiso.coordination.Snapshot;
import io.iaiso.policy.Policy;
import io.iaiso.policy.PolicyLoader;
import io.iaiso.policy.SumAggregator;

import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Arrays;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/** IAIso admin CLI. */
public final class Main {

    private static final Gson PRETTY = new GsonBuilder().setPrettyPrinting().create();

    public static void main(String[] argv) {
        int code = run(argv);
        System.exit(code);
    }

    /** Run the CLI with the given args. Returns a process exit code. */
    public static int run(String[] argv) {
        if (argv.length == 0 || "--help".equals(argv[0]) || "-h".equals(argv[0])) {
            printHelp();
            return 0;
        }
        String[] rest = Arrays.copyOfRange(argv, 1, argv.length);
        switch (argv[0]) {
            case "policy": return cmdPolicy(rest);
            case "consent": return cmdConsent(rest);
            case "audit": return cmdAudit(rest);
            case "coordinator": return cmdCoordinator(rest);
            case "conformance": return cmdConformance(rest);
            default:
                System.err.println("unknown command: " + argv[0]);
                printHelp();
                return 2;
        }
    }

    private static void printHelp() {
        System.out.println(
            "IAIso admin CLI\n" +
            "\n" +
            "Subcommands:\n" +
            "  policy validate <file>                 check a policy JSON file for errors\n" +
            "  policy template <file>                 write a blank policy template\n" +
            "  consent issue <sub> <scope,...> [ttl]  issue a token (needs IAISO_HS256_SECRET)\n" +
            "  consent verify <token>                 verify a token\n" +
            "  audit tail <jsonl-file>                pretty-print JSONL audit events\n" +
            "  audit stats <jsonl-file>               summarize events by kind\n" +
            "  coordinator demo                       in-memory coordinator smoke test\n" +
            "  conformance <spec-dir>                 run the conformance suite");
    }

    private static int cmdPolicy(String[] args) {
        if (args.length == 0) {
            System.err.println("usage: iaiso policy [validate|template] <file>");
            return 2;
        }
        switch (args[0]) {
            case "validate":
                if (args.length != 2) {
                    System.err.println("usage: iaiso policy validate <file>");
                    return 2;
                }
                try {
                    Policy p = PolicyLoader.load(Paths.get(args[1]));
                    System.out.println("OK: policy v" + p.getVersion());
                    System.out.println("  pressure.escalation_threshold = "
                        + p.getPressure().getEscalationThreshold());
                    System.out.println("  coordinator.aggregator        = "
                        + p.getAggregator().name());
                    System.out.println("  consent.issuer                = "
                        + (p.getConsent().getIssuer() != null
                            ? p.getConsent().getIssuer() : "(none)"));
                    return 0;
                } catch (RuntimeException e) {
                    System.err.println("INVALID: " + e.getMessage());
                    return 1;
                }
            case "template":
                if (args.length != 2) {
                    System.err.println("usage: iaiso policy template <file>");
                    return 2;
                }
                String body =
                    "{\n" +
                    "  \"version\": \"1\",\n" +
                    "  \"pressure\": {\n" +
                    "    \"escalation_threshold\": 0.85,\n" +
                    "    \"release_threshold\": 0.95,\n" +
                    "    \"token_coefficient\": 0.015,\n" +
                    "    \"tool_coefficient\": 0.08,\n" +
                    "    \"depth_coefficient\": 0.05,\n" +
                    "    \"dissipation_per_step\": 0.02,\n" +
                    "    \"dissipation_per_second\": 0.0,\n" +
                    "    \"post_release_lock\": true\n" +
                    "  },\n" +
                    "  \"coordinator\": {\n" +
                    "    \"aggregator\": \"sum\",\n" +
                    "    \"escalation_threshold\": 5.0,\n" +
                    "    \"release_threshold\": 8.0,\n" +
                    "    \"notify_cooldown_seconds\": 1.0\n" +
                    "  },\n" +
                    "  \"consent\": {\n" +
                    "    \"issuer\": \"iaiso\",\n" +
                    "    \"default_ttl_seconds\": 3600,\n" +
                    "    \"required_scopes\": [],\n" +
                    "    \"allowed_algorithms\": [\"HS256\", \"RS256\"]\n" +
                    "  },\n" +
                    "  \"metadata\": {}\n" +
                    "}\n";
                try {
                    Files.writeString(Paths.get(args[1]), body);
                    System.out.println("Wrote template to " + args[1]);
                    return 0;
                } catch (IOException e) {
                    System.err.println("write " + args[1] + ": " + e.getMessage());
                    return 1;
                }
            default:
                System.err.println("unknown policy subcommand: " + args[0]);
                return 2;
        }
    }

    private static int cmdConsent(String[] args) {
        if (args.length == 0) {
            System.err.println("usage: iaiso consent [issue|verify] ...");
            return 2;
        }
        String secret = System.getenv("IAISO_HS256_SECRET");
        if (secret == null || secret.isEmpty()) {
            System.err.println("error: IAISO_HS256_SECRET must be set in the environment");
            return 2;
        }
        switch (args[0]) {
            case "issue": {
                if (args.length < 3) {
                    System.err.println(
                        "usage: iaiso consent issue <subject> <scope1,scope2,...> [ttl_seconds]");
                    return 2;
                }
                long ttl = args.length > 3 ? Long.parseLong(args[3]) : 3600L;
                List<String> scopes = Arrays.stream(args[2].split(","))
                    .map(String::trim).filter(s -> !s.isEmpty())
                    .collect(java.util.stream.Collectors.toList());
                Issuer issuer = Issuer.builder()
                    .hsKey(secret.getBytes())
                    .algorithm(Algorithm.HS256)
                    .issuer("iaiso")
                    .defaultTtlSeconds(ttl)
                    .build();
                try {
                    Scope scope = issuer.issue(args[1], scopes, null, ttl, null);
                    JsonObject out = new JsonObject();
                    out.addProperty("token", scope.getToken());
                    out.addProperty("subject", scope.getSubject());
                    com.google.gson.JsonArray sc = new com.google.gson.JsonArray();
                    scope.getScopes().forEach(sc::add);
                    out.add("scopes", sc);
                    out.addProperty("jti", scope.getJti());
                    out.addProperty("expires_at", scope.getExpiresAt());
                    System.out.println(PRETTY.toJson(out));
                    return 0;
                } catch (RuntimeException e) {
                    System.err.println("issue failed: " + e.getMessage());
                    return 1;
                }
            }
            case "verify": {
                if (args.length != 2) {
                    System.err.println("usage: iaiso consent verify <token>");
                    return 2;
                }
                Verifier verifier = Verifier.builder()
                    .hsKey(secret.getBytes())
                    .algorithm(Algorithm.HS256)
                    .issuer("iaiso")
                    .build();
                try {
                    Scope s = verifier.verify(args[1], null);
                    JsonObject out = new JsonObject();
                    out.addProperty("status", "valid");
                    out.addProperty("subject", s.getSubject());
                    com.google.gson.JsonArray sc = new com.google.gson.JsonArray();
                    s.getScopes().forEach(sc::add);
                    out.add("scopes", sc);
                    out.addProperty("jti", s.getJti());
                    out.addProperty("expires_at", s.getExpiresAt());
                    if (s.getExecutionId() != null) {
                        out.addProperty("execution_id", s.getExecutionId());
                    }
                    System.out.println(PRETTY.toJson(out));
                    return 0;
                } catch (ConsentException.ExpiredToken e) {
                    System.err.println("expired: " + e.getMessage());
                    return 1;
                } catch (ConsentException.RevokedToken e) {
                    System.err.println("revoked: " + e.getMessage());
                    return 1;
                } catch (RuntimeException e) {
                    System.err.println("invalid: " + e.getMessage());
                    return 1;
                }
            }
            default:
                System.err.println("unknown consent subcommand: " + args[0]);
                return 2;
        }
    }

    private static int cmdAudit(String[] args) {
        if (args.length == 0) {
            System.err.println("usage: iaiso audit [tail|stats] <jsonl-file>");
            return 2;
        }
        switch (args[0]) {
            case "tail":
                if (args.length != 2) {
                    System.err.println("usage: iaiso audit tail <jsonl-file>");
                    return 2;
                }
                return tailJsonl(Paths.get(args[1]));
            case "stats":
                if (args.length != 2) {
                    System.err.println("usage: iaiso audit stats <jsonl-file>");
                    return 2;
                }
                return statsJsonl(Paths.get(args[1]));
            default:
                System.err.println("unknown audit subcommand: " + args[0]);
                return 2;
        }
    }

    private static int tailJsonl(Path path) {
        try {
            for (String line : Files.readAllLines(path)) {
                line = line.trim();
                if (line.isEmpty()) continue;
                try {
                    JsonObject ev = com.google.gson.JsonParser.parseString(line).getAsJsonObject();
                    String ts = ev.has("timestamp")
                        ? String.format("%.3f", ev.get("timestamp").getAsDouble()) : "?";
                    String kind = ev.has("kind") ? ev.get("kind").getAsString() : "?";
                    String exec = ev.has("execution_id") ? ev.get("execution_id").getAsString() : "?";
                    System.out.printf("%-15s  %-28s  %s%n", ts, kind, exec);
                } catch (RuntimeException ex) {
                    String trunc = line.length() > 80 ? line.substring(0, 80) : line;
                    System.out.println("  [unparseable] " + trunc);
                }
            }
            return 0;
        } catch (IOException e) {
            System.err.println("open " + path + ": " + e.getMessage());
            return 1;
        }
    }

    private static int statsJsonl(Path path) {
        try {
            Map<String, Integer> counts = new TreeMap<>();
            java.util.Set<String> executions = new java.util.HashSet<>();
            int total = 0;
            for (String line : Files.readAllLines(path)) {
                line = line.trim();
                if (line.isEmpty()) continue;
                try {
                    JsonObject ev = com.google.gson.JsonParser.parseString(line).getAsJsonObject();
                    total++;
                    if (ev.has("kind")) {
                        String k = ev.get("kind").getAsString();
                        counts.merge(k, 1, Integer::sum);
                    }
                    if (ev.has("execution_id")) {
                        executions.add(ev.get("execution_id").getAsString());
                    }
                } catch (RuntimeException ignored) {}
            }
            System.out.println("total events: " + total);
            System.out.println("distinct executions: " + executions.size());
            counts.entrySet().stream()
                .sorted((a, b) -> b.getValue().compareTo(a.getValue()))
                .forEach(e -> System.out.printf("  %6d  %s%n", e.getValue(), e.getKey()));
            return 0;
        } catch (IOException e) {
            System.err.println("open " + path + ": " + e.getMessage());
            return 1;
        }
    }

    private static int cmdCoordinator(String[] args) {
        if (args.length == 0 || !"demo".equals(args[0])) {
            System.err.println("usage: iaiso coordinator demo");
            return 2;
        }
        SharedPressureCoordinator c = SharedPressureCoordinator.builder()
            .coordinatorId("cli-demo")
            .escalationThreshold(1.5)
            .releaseThreshold(2.5)
            .notifyCooldownSeconds(0.0)
            .aggregator(new SumAggregator())
            .auditSink(new MemorySink())
            .onEscalation(s -> System.out.printf(
                "  [callback] ESCALATION at aggregate=%.3f%n", s.getAggregatePressure()))
            .onRelease(s -> System.out.printf(
                "  [callback] RELEASE at aggregate=%.3f%n", s.getAggregatePressure()))
            .clock(() -> 0.0)
            .build();
        String[] workers = {"worker-a", "worker-b", "worker-c"};
        for (String w : workers) c.register(w);
        System.out.println("Demo: 3 workers registered. Stepping pressures...");
        double[] steps = {0.3, 0.6, 0.9, 0.6};
        for (int i = 0; i < steps.length; i++) {
            for (String w : workers) c.update(w, steps[i]);
            Snapshot snap = c.snapshot();
            System.out.printf("  step %d: per-worker=%.2f  aggregate=%.3f  lifecycle=%s%n",
                i + 1, steps[i], snap.getAggregatePressure(), snap.getLifecycle());
        }
        return 0;
    }

    private static int cmdConformance(String[] args) {
        Path specRoot = args.length > 0 ? Paths.get(args[0]) : Paths.get("./spec");
        try {
            SectionResults r = ConformanceRunner.runAll(specRoot);
            int fail = 0;
            String[] sectionNames = {"pressure", "consent", "events", "policy"};
            List<List<VectorResult>> sections = Arrays.asList(
                r.pressure, r.consent, r.events, r.policy);
            for (int i = 0; i < sectionNames.length; i++) {
                List<VectorResult> bucket = sections.get(i);
                long pass = bucket.stream().filter(v -> v.passed).count();
                int total = bucket.size();
                String marker = pass == total ? "PASS" : "FAIL";
                if (pass != total) {
                    fail += total - pass;
                    for (VectorResult v : bucket) {
                        if (!v.passed) {
                            System.out.println("  [" + sectionNames[i] + "] "
                                + v.name + ": " + v.message);
                        }
                    }
                }
                System.out.println("[" + marker + "] " + sectionNames[i]
                    + ": " + pass + "/" + total);
            }
            int passed = r.countPassed();
            int total = r.countTotal();
            System.out.println("\nconformance: " + passed + "/" + total + " vectors passed");
            return fail > 0 ? 1 : 0;
        } catch (IOException e) {
            System.err.println("error: " + e.getMessage());
            return 1;
        }
    }
}
