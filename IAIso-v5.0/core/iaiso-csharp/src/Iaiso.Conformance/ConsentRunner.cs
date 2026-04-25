using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json.Nodes;
using Iaiso.Consent;

namespace Iaiso.Conformance;

internal static class ConsentRunner
{
    public static List<VectorResult> Run(string specRoot)
    {
        var path = Path.Combine(specRoot, "consent", "vectors.json");
        var doc = JsonNode.Parse(File.ReadAllBytes(path))!.AsObject();
        string sharedKey = doc["hs256_key_shared"]!.GetValue<string>();

        var results = new List<VectorResult>();
        if (doc["scope_match"] is JsonArray sm)
            foreach (var v in sm) results.Add(RunScopeMatch(v!.AsObject()));
        if (doc["scope_match_errors"] is JsonArray sme)
            foreach (var v in sme) results.Add(RunScopeMatchError(v!.AsObject()));
        if (doc["valid_tokens"] is JsonArray vt)
            foreach (var v in vt) results.Add(RunValidToken(sharedKey, v!.AsObject()));
        if (doc["invalid_tokens"] is JsonArray it)
            foreach (var v in it) results.Add(RunInvalidToken(sharedKey, v!.AsObject()));
        if (doc["issue_and_verify_roundtrip"] is JsonArray rt)
            foreach (var v in rt) results.Add(RunRoundtrip(sharedKey, v!.AsObject()));
        return results;
    }

    private static VectorResult RunScopeMatch(JsonObject v)
    {
        string name = "scope_match/" + v["name"]!.GetValue<string>();
        var granted = new List<string>();
        foreach (var g in v["granted"]!.AsArray()) granted.Add(g!.GetValue<string>());
        string requested = v["requested"]!.GetValue<string>();
        bool expected = v["expected"]!.GetValue<bool>();
        try
        {
            bool got = Scopes.Granted(granted, requested);
            return got == expected
                ? VectorResult.Pass("consent", name)
                : VectorResult.Fail("consent", name, $"got {got}, want {expected}");
        }
        catch (Exception e)
        {
            return VectorResult.Fail("consent", name, "unexpected exception: " + e.Message);
        }
    }

    private static VectorResult RunScopeMatchError(JsonObject v)
    {
        string name = "scope_match_errors/" + v["name"]!.GetValue<string>();
        var granted = new List<string>();
        foreach (var g in v["granted"]!.AsArray()) granted.Add(g!.GetValue<string>());
        string requested = v["requested"]!.GetValue<string>();
        string expectErr = v["expect_error"]!.GetValue<string>();
        try
        {
            Scopes.Granted(granted, requested);
            return VectorResult.Fail("consent", name,
                $"expected error containing '{expectErr}', got Ok");
        }
        catch (ArgumentException e)
        {
            string msg = e.Message.ToLowerInvariant();
            return msg.Contains(expectErr.ToLowerInvariant())
                ? VectorResult.Pass("consent", name)
                : VectorResult.Fail("consent", name,
                    $"expected error containing '{expectErr}', got: {e.Message}");
        }
    }

    private static Algorithm ParseAlg(JsonObject v)
    {
        if (v["algorithm"] is JsonValue av && av.TryGetValue<string>(out var s))
        {
            try { return AlgorithmExtensions.ParseAlgorithm(s); } catch { }
        }
        return Algorithm.HS256;
    }

    private static string? StringOrDefault(JsonObject v, string key, string? dflt)
    {
        if (v[key] is JsonValue jv && jv.TryGetValue<string>(out var s)) return s;
        return dflt;
    }

    private static VectorResult RunValidToken(string sharedKey, JsonObject v)
    {
        string name = "valid_tokens/" + v["name"]!.GetValue<string>();
        long now = v["now"]!.GetValue<long>();
        string issuer = StringOrDefault(v, "issuer", "iaiso") ?? "iaiso";
        var alg = ParseAlg(v);
        string token = v["token"]!.GetValue<string>();
        var expected = v["expected"]!.AsObject();

        var verifier = Verifier.CreateBuilder()
            .WithHsKey(Encoding.UTF8.GetBytes(sharedKey))
            .WithAlgorithm(alg)
            .WithIssuer(issuer)
            .WithClock(() => now)
            .Build();
        try
        {
            var s = verifier.Verify(token, null);
            string wantSub = expected["sub"]!.GetValue<string>();
            if (s.Subject != wantSub)
                return VectorResult.Fail("consent", name, $"sub: got {s.Subject}, want {wantSub}");
            string wantJti = expected["jti"]!.GetValue<string>();
            if (s.Jti != wantJti)
                return VectorResult.Fail("consent", name, $"jti: got {s.Jti}, want {wantJti}");
            var wantScopes = new List<string>();
            foreach (var n in expected["scopes"]!.AsArray()) wantScopes.Add(n!.GetValue<string>());
            if (!ListEquals(s.Scopes, wantScopes))
                return VectorResult.Fail("consent", name, "scopes mismatch");
            string? wantExec = expected["execution_id"] is JsonValue ev
                && ev.TryGetValue<string>(out var es) ? es : null;
            if (wantExec is null ? s.ExecutionId is not null : wantExec != s.ExecutionId)
                return VectorResult.Fail("consent", name,
                    $"execution_id: got {s.ExecutionId}, want {wantExec}");
            return VectorResult.Pass("consent", name);
        }
        catch (Exception e)
        {
            return VectorResult.Fail("consent", name, "verify failed: " + e.Message);
        }
    }

    private static VectorResult RunInvalidToken(string sharedKey, JsonObject v)
    {
        string name = "invalid_tokens/" + v["name"]!.GetValue<string>();
        long now = v["now"]!.GetValue<long>();
        string issuer = StringOrDefault(v, "issuer", "iaiso") ?? "iaiso";
        var alg = ParseAlg(v);
        string token = v["token"]!.GetValue<string>();
        string? execId = StringOrDefault(v, "execution_id", null);
        string expectErr = v["expect_error"]!.GetValue<string>();

        var verifier = Verifier.CreateBuilder()
            .WithHsKey(Encoding.UTF8.GetBytes(sharedKey))
            .WithAlgorithm(alg)
            .WithIssuer(issuer)
            .WithClock(() => now)
            .Build();
        try
        {
            verifier.Verify(token, execId);
            return VectorResult.Fail("consent", name,
                $"expected error '{expectErr}', got Ok");
        }
        catch (ExpiredTokenException)
        {
            return expectErr == "expired"
                ? VectorResult.Pass("consent", name)
                : VectorResult.Fail("consent", name, $"expected '{expectErr}', got expired");
        }
        catch (RevokedTokenException)
        {
            return expectErr == "revoked"
                ? VectorResult.Pass("consent", name)
                : VectorResult.Fail("consent", name, $"expected '{expectErr}', got revoked");
        }
        catch (InvalidTokenException e)
        {
            return expectErr == "invalid"
                ? VectorResult.Pass("consent", name)
                : VectorResult.Fail("consent", name,
                    $"expected '{expectErr}', got invalid: {e.Message}");
        }
        catch (Exception e)
        {
            return VectorResult.Fail("consent", name,
                $"unexpected exception type: {e.GetType().Name}: {e.Message}");
        }
    }

    private static VectorResult RunRoundtrip(string sharedKey, JsonObject v)
    {
        string name = "roundtrip/" + v["name"]!.GetValue<string>();
        var issueSpec = v["issue"]!.AsObject();
        long ttl = issueSpec["ttl_seconds"]?.GetValue<long>() ?? 3600;
        string subject = issueSpec["subject"]!.GetValue<string>();
        var scopes = new List<string>();
        foreach (var n in issueSpec["scopes"]!.AsArray()) scopes.Add(n!.GetValue<string>());
        string? execId = StringOrDefault(issueSpec, "execution_id", null);
        var metadata = issueSpec["metadata"] as JsonObject;

        long now = v["now"] is JsonValue nv && nv.TryGetValue<long>(out var nt) ? nt : 1_700_000_000L;
        string issuer = StringOrDefault(v, "issuer", "iaiso") ?? "iaiso";
        var alg = ParseAlg(v);

        var iss = Issuer.CreateBuilder()
            .WithHsKey(Encoding.UTF8.GetBytes(sharedKey))
            .WithAlgorithm(alg)
            .WithIssuer(issuer)
            .WithClock(() => now)
            .Build();
        Scope scope;
        try { scope = iss.Issue(subject, scopes, execId, ttl, metadata); }
        catch (Exception e)
        {
            return VectorResult.Fail("consent", name, "issue failed: " + e.Message);
        }

        bool expectSuccess = v["expected_after_verify_succeeds"]?.GetValue<bool>() ?? false;
        string? verifyExec = StringOrDefault(v, "verify_with_execution_id", null);

        var ver = Verifier.CreateBuilder()
            .WithHsKey(Encoding.UTF8.GetBytes(sharedKey))
            .WithAlgorithm(alg)
            .WithIssuer(issuer)
            .WithClock(() => now + 1)
            .Build();
        try
        {
            var verified = ver.Verify(scope.Token, verifyExec);
            if (!expectSuccess)
                return VectorResult.Fail("consent", name, "expected verify to fail, succeeded");
            if (verified.Subject != subject)
                return VectorResult.Fail("consent", name, "subject mismatch");
            if (!ListEquals(verified.Scopes, scopes))
                return VectorResult.Fail("consent", name, "scopes mismatch");
            return VectorResult.Pass("consent", name);
        }
        catch (Exception e)
        {
            return expectSuccess
                ? VectorResult.Fail("consent", name, "expected verify to succeed, failed: " + e.Message)
                : VectorResult.Pass("consent", name);
        }
    }

    private static bool ListEquals(IReadOnlyList<string> a, IReadOnlyList<string> b)
    {
        if (a.Count != b.Count) return false;
        for (int i = 0; i < a.Count; i++) if (a[i] != b[i]) return false;
        return true;
    }
}
