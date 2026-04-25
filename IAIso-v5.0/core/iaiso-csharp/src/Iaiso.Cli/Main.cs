using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Nodes;
using Iaiso.Audit;
using Iaiso.Conformance;
using Iaiso.Consent;
using Iaiso.Coordination;
using Iaiso.Policy;

namespace Iaiso.Cli;

internal static class Main_
{
    private static readonly JsonSerializerOptions Pretty = new() { WriteIndented = true };

    private static int Main(string[] argv)
    {
        if (argv.Length == 0 || argv[0] == "--help" || argv[0] == "-h")
        {
            PrintHelp();
            return 0;
        }
        var rest = argv[1..];
        return argv[0] switch
        {
            "policy" => CmdPolicy(rest),
            "consent" => CmdConsent(rest),
            "audit" => CmdAudit(rest),
            "coordinator" => CmdCoordinator(rest),
            "conformance" => CmdConformance(rest),
            _ => UnknownCommand(argv[0]),
        };
    }

    private static int UnknownCommand(string c)
    {
        Console.Error.WriteLine($"unknown command: {c}");
        PrintHelp();
        return 2;
    }

    private static void PrintHelp()
    {
        Console.WriteLine(
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

    private static int CmdPolicy(string[] args)
    {
        if (args.Length == 0) { Console.Error.WriteLine("usage: iaiso policy [validate|template] <file>"); return 2; }
        switch (args[0])
        {
            case "validate":
                if (args.Length != 2) { Console.Error.WriteLine("usage: iaiso policy validate <file>"); return 2; }
                try
                {
                    var p = PolicyLoader.Load(args[1]);
                    Console.WriteLine($"OK: policy v{p.Version}");
                    Console.WriteLine($"  pressure.escalation_threshold = {p.Pressure.EscalationThreshold}");
                    Console.WriteLine($"  coordinator.aggregator        = {p.Aggregator.Name}");
                    Console.WriteLine($"  consent.issuer                = {p.Consent.Issuer ?? "(none)"}");
                    return 0;
                }
                catch (Exception e)
                {
                    Console.Error.WriteLine($"INVALID: {e.Message}");
                    return 1;
                }
            case "template":
                if (args.Length != 2) { Console.Error.WriteLine("usage: iaiso policy template <file>"); return 2; }
                try
                {
                    File.WriteAllText(args[1], TemplateBody);
                    Console.WriteLine($"Wrote template to {args[1]}");
                    return 0;
                }
                catch (IOException e)
                {
                    Console.Error.WriteLine($"write {args[1]}: {e.Message}");
                    return 1;
                }
            default:
                Console.Error.WriteLine($"unknown policy subcommand: {args[0]}");
                return 2;
        }
    }

    private const string TemplateBody = """
{
  "version": "1",
  "pressure": {
    "escalation_threshold": 0.85,
    "release_threshold": 0.95,
    "token_coefficient": 0.015,
    "tool_coefficient": 0.08,
    "depth_coefficient": 0.05,
    "dissipation_per_step": 0.02,
    "dissipation_per_second": 0.0,
    "post_release_lock": true
  },
  "coordinator": {
    "aggregator": "sum",
    "escalation_threshold": 5.0,
    "release_threshold": 8.0,
    "notify_cooldown_seconds": 1.0
  },
  "consent": {
    "issuer": "iaiso",
    "default_ttl_seconds": 3600,
    "required_scopes": [],
    "allowed_algorithms": ["HS256", "RS256"]
  },
  "metadata": {}
}
""";

    private static int CmdConsent(string[] args)
    {
        if (args.Length == 0) { Console.Error.WriteLine("usage: iaiso consent [issue|verify] ..."); return 2; }
        string? secret = Environment.GetEnvironmentVariable("IAISO_HS256_SECRET");
        if (string.IsNullOrEmpty(secret))
        {
            Console.Error.WriteLine("error: IAISO_HS256_SECRET must be set in the environment");
            return 2;
        }
        switch (args[0])
        {
            case "issue":
                if (args.Length < 3) { Console.Error.WriteLine("usage: iaiso consent issue <subject> <scope1,scope2,...> [ttl_seconds]"); return 2; }
                long ttl = args.Length > 3 ? long.Parse(args[3], CultureInfo.InvariantCulture) : 3600L;
                var scopes = args[2].Split(',', StringSplitOptions.RemoveEmptyEntries);
                var issuer = Issuer.CreateBuilder()
                    .WithHsKey(Encoding.UTF8.GetBytes(secret))
                    .WithAlgorithm(Algorithm.HS256)
                    .WithIssuer("iaiso")
                    .WithDefaultTtlSeconds(ttl)
                    .Build();
                try
                {
                    var scope = issuer.Issue(args[1], scopes, null, ttl, null);
                    var outDict = new Dictionary<string, object>
                    {
                        ["token"] = scope.Token,
                        ["subject"] = scope.Subject,
                        ["scopes"] = scope.Scopes,
                        ["jti"] = scope.Jti,
                        ["expires_at"] = scope.ExpiresAt,
                    };
                    Console.WriteLine(JsonSerializer.Serialize(outDict, Pretty));
                    return 0;
                }
                catch (Exception e)
                {
                    Console.Error.WriteLine($"issue failed: {e.Message}");
                    return 1;
                }
            case "verify":
                if (args.Length != 2) { Console.Error.WriteLine("usage: iaiso consent verify <token>"); return 2; }
                var verifier = Verifier.CreateBuilder()
                    .WithHsKey(Encoding.UTF8.GetBytes(secret))
                    .WithAlgorithm(Algorithm.HS256)
                    .WithIssuer("iaiso")
                    .Build();
                try
                {
                    var s = verifier.Verify(args[1], null);
                    var outDict = new Dictionary<string, object?>
                    {
                        ["status"] = "valid",
                        ["subject"] = s.Subject,
                        ["scopes"] = s.Scopes,
                        ["jti"] = s.Jti,
                        ["expires_at"] = s.ExpiresAt,
                    };
                    if (s.ExecutionId is not null) outDict["execution_id"] = s.ExecutionId;
                    Console.WriteLine(JsonSerializer.Serialize(outDict, Pretty));
                    return 0;
                }
                catch (ExpiredTokenException e) { Console.Error.WriteLine($"expired: {e.Message}"); return 1; }
                catch (RevokedTokenException e) { Console.Error.WriteLine($"revoked: {e.Message}"); return 1; }
                catch (Exception e) { Console.Error.WriteLine($"invalid: {e.Message}"); return 1; }
            default:
                Console.Error.WriteLine($"unknown consent subcommand: {args[0]}");
                return 2;
        }
    }

    private static int CmdAudit(string[] args)
    {
        if (args.Length == 0) { Console.Error.WriteLine("usage: iaiso audit [tail|stats] <jsonl-file>"); return 2; }
        switch (args[0])
        {
            case "tail":
                if (args.Length != 2) { Console.Error.WriteLine("usage: iaiso audit tail <jsonl-file>"); return 2; }
                return TailJsonl(args[1]);
            case "stats":
                if (args.Length != 2) { Console.Error.WriteLine("usage: iaiso audit stats <jsonl-file>"); return 2; }
                return StatsJsonl(args[1]);
            default:
                Console.Error.WriteLine($"unknown audit subcommand: {args[0]}");
                return 2;
        }
    }

    private static int TailJsonl(string path)
    {
        try
        {
            foreach (var lineRaw in File.ReadAllLines(path))
            {
                var line = lineRaw.Trim();
                if (line.Length == 0) continue;
                try
                {
                    var ev = JsonNode.Parse(line)!.AsObject();
                    string ts = ev["timestamp"] is JsonValue tv && tv.TryGetValue<double>(out var t)
                        ? t.ToString("F3", CultureInfo.InvariantCulture) : "?";
                    string kind = ev["kind"]?.GetValue<string>() ?? "?";
                    string exec = ev["execution_id"]?.GetValue<string>() ?? "?";
                    Console.WriteLine($"{ts,-15}  {kind,-28}  {exec}");
                }
                catch
                {
                    Console.WriteLine("  [unparseable] " + (line.Length > 80 ? line[..80] : line));
                }
            }
            return 0;
        }
        catch (IOException e)
        {
            Console.Error.WriteLine($"open {path}: {e.Message}");
            return 1;
        }
    }

    private static int StatsJsonl(string path)
    {
        try
        {
            var counts = new SortedDictionary<string, int>();
            var executions = new HashSet<string>();
            int total = 0;
            foreach (var lineRaw in File.ReadAllLines(path))
            {
                var line = lineRaw.Trim();
                if (line.Length == 0) continue;
                try
                {
                    var ev = JsonNode.Parse(line)!.AsObject();
                    total++;
                    if (ev["kind"]?.GetValue<string>() is string k)
                        counts[k] = counts.TryGetValue(k, out var n) ? n + 1 : 1;
                    if (ev["execution_id"]?.GetValue<string>() is string ex)
                        executions.Add(ex);
                }
                catch { /* ignore */ }
            }
            Console.WriteLine($"total events: {total}");
            Console.WriteLine($"distinct executions: {executions.Count}");
            var sorted = new List<KeyValuePair<string, int>>(counts);
            sorted.Sort((a, b) => b.Value.CompareTo(a.Value));
            foreach (var kv in sorted)
                Console.WriteLine($"  {kv.Value,6}  {kv.Key}");
            return 0;
        }
        catch (IOException e)
        {
            Console.Error.WriteLine($"open {path}: {e.Message}");
            return 1;
        }
    }

    private static int CmdCoordinator(string[] args)
    {
        if (args.Length == 0 || args[0] != "demo")
        {
            Console.Error.WriteLine("usage: iaiso coordinator demo");
            return 2;
        }
        var c = SharedPressureCoordinator.CreateBuilder()
            .WithCoordinatorId("cli-demo")
            .WithEscalationThreshold(1.5)
            .WithReleaseThreshold(2.5)
            .WithNotifyCooldownSeconds(0.0)
            .WithAggregator(new SumAggregator())
            .WithAuditSink(new MemorySink())
            .WithOnEscalation(s => Console.WriteLine(
                $"  [callback] ESCALATION at aggregate={s.AggregatePressure:F3}"))
            .WithOnRelease(s => Console.WriteLine(
                $"  [callback] RELEASE at aggregate={s.AggregatePressure:F3}"))
            .WithClock(new DelegateCoordClock(() => 0.0))
            .Build();
        var workers = new[] { "worker-a", "worker-b", "worker-c" };
        foreach (var w in workers) c.Register(w);
        Console.WriteLine("Demo: 3 workers registered. Stepping pressures...");
        var steps = new[] { 0.3, 0.6, 0.9, 0.6 };
        for (int i = 0; i < steps.Length; i++)
        {
            foreach (var w in workers) c.Update(w, steps[i]);
            var snap = c.Snapshot();
            Console.WriteLine(
                $"  step {i + 1}: per-worker={steps[i]:F2}  aggregate={snap.AggregatePressure:F3}  lifecycle={snap.Lifecycle.Wire()}");
        }
        return 0;
    }

    private static int CmdConformance(string[] args)
    {
        string specRoot = args.Length > 0 ? args[0] : "./spec";
        try
        {
            var r = ConformanceRunner.RunAll(specRoot);
            int fail = 0;
            var sectionNames = new[] { "pressure", "consent", "events", "policy" };
            var sections = new[] { r.Pressure, r.Consent, r.Events, r.Policy };
            for (int i = 0; i < sectionNames.Length; i++)
            {
                var bucket = sections[i];
                int pass = 0;
                foreach (var v in bucket) if (v.Passed) pass++;
                int total = bucket.Count;
                string marker = pass == total ? "PASS" : "FAIL";
                if (pass != total)
                {
                    fail += total - pass;
                    foreach (var v in bucket)
                        if (!v.Passed) Console.WriteLine($"  [{sectionNames[i]}] {v.Name}: {v.Message}");
                }
                Console.WriteLine($"[{marker}] {sectionNames[i]}: {pass}/{total}");
            }
            Console.WriteLine();
            Console.WriteLine($"conformance: {r.CountPassed()}/{r.CountTotal()} vectors passed");
            return fail > 0 ? 1 : 0;
        }
        catch (Exception e)
        {
            Console.Error.WriteLine($"error: {e.Message}");
            return 1;
        }
    }
}
