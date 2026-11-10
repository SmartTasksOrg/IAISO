using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;
using System.Threading;
using Iaiso.Consent;

namespace Iaiso.Identity;

public class IdentityException : Exception
{
    public IdentityException(string message) : base(message) {}
    public IdentityException(string message, Exception inner) : base(message, inner) {}
}

/// <summary>Configuration for an <see cref="OidcVerifier"/>.</summary>
public sealed class ProviderConfig
{
    public string? DiscoveryUrl { get; }
    public string? JwksUrl { get; }
    public string? Issuer { get; }
    public string? Audience { get; }
    public IReadOnlyList<string> AllowedAlgorithms { get; }
    public long LeewaySeconds { get; }

    public ProviderConfig(string? discoveryUrl, string? jwksUrl, string? issuer, string? audience,
                          IReadOnlyList<string>? allowedAlgorithms, long leewaySeconds)
    {
        DiscoveryUrl = discoveryUrl;
        JwksUrl = jwksUrl;
        Issuer = issuer;
        Audience = audience;
        AllowedAlgorithms = allowedAlgorithms ?? new List<string> { "RS256" };
        LeewaySeconds = leewaySeconds;
    }

    public static ProviderConfig Defaults() => new(null, null, null, null,
        new List<string> { "RS256" }, 5);

    /// <summary>Build a <see cref="ProviderConfig"/> for Okta.</summary>
    public static ProviderConfig Okta(string domain, string audience) =>
        new($"https://{domain}/.well-known/openid-configuration",
            null, $"https://{domain}", audience,
            new List<string> { "RS256" }, 5);

    /// <summary>Build a <see cref="ProviderConfig"/> for Auth0.</summary>
    public static ProviderConfig Auth0(string domain, string audience) =>
        new($"https://{domain}/.well-known/openid-configuration",
            null, $"https://{domain}/", audience,
            new List<string> { "RS256" }, 5);

    /// <summary>Build a <see cref="ProviderConfig"/> for Azure AD / Entra.</summary>
    public static ProviderConfig AzureAd(string tenant, string audience, bool v2 = true)
    {
        string @base = v2
            ? $"https://login.microsoftonline.com/{tenant}/v2.0"
            : $"https://login.microsoftonline.com/{tenant}";
        return new ProviderConfig(
            $"{@base}/.well-known/openid-configuration",
            null, @base, audience, new List<string> { "RS256" }, 5);
    }
}

/// <summary>Configures how OIDC claims become IAIso scopes.</summary>
public sealed class ScopeMapping
{
    public IReadOnlyList<string> DirectClaims { get; }
    public IReadOnlyDictionary<string, IReadOnlyList<string>> GroupToScopes { get; }
    public IReadOnlyList<string> AlwaysGrant { get; }

    public ScopeMapping(IReadOnlyList<string>? directClaims,
                        IReadOnlyDictionary<string, IReadOnlyList<string>>? groupToScopes,
                        IReadOnlyList<string>? alwaysGrant)
    {
        DirectClaims = directClaims ?? new List<string>();
        GroupToScopes = groupToScopes ?? new Dictionary<string, IReadOnlyList<string>>();
        AlwaysGrant = alwaysGrant ?? new List<string>();
    }

    public static ScopeMapping Defaults() => new(null, null, null);
}

/// <summary>A single key from a JWKS document.</summary>
public sealed class Jwk
{
    public string Kty { get; }
    public string Kid { get; }
    public string? Alg { get; }
    public string? Use { get; }
    public string? N { get; }
    public string? E { get; }

    public Jwk(string kty, string kid, string? alg, string? use, string? n, string? e)
    {
        Kty = kty; Kid = kid; Alg = alg; Use = use; N = n; E = e;
    }
}

public sealed class Jwks
{
    public IReadOnlyList<Jwk> Keys { get; }
    public Jwks(IReadOnlyList<Jwk> keys) { Keys = new List<Jwk>(keys); }
}

/// <summary>
/// IAIso OIDC identity verifier.
///
/// This module is HTTP-free. Caller fetches the JWKS bytes (using
/// <see cref="System.Net.Http.HttpClient"/> or any HTTP library) and
/// passes them to <see cref="SetJwksFromBytes(byte[])"/>. This keeps
/// the SDK dependency-light and lets users use whichever HTTP client
/// they prefer.
/// </summary>
public sealed class OidcVerifier
{
    private readonly ProviderConfig _cfg;
    private readonly ReaderWriterLockSlim _lock = new();
    private Jwks? _jwks;

    public OidcVerifier(ProviderConfig cfg) { _cfg = cfg; }

    /// <summary>Inject pre-fetched JWKS bytes into the verifier's cache.</summary>
    public void SetJwksFromBytes(byte[] body)
    {
        try
        {
            var root = JsonNode.Parse(body)!.AsObject();
            var keysArr = root["keys"]!.AsArray();
            var keys = new List<Jwk>(keysArr.Count);
            foreach (var el in keysArr)
            {
                var k = el!.AsObject();
                keys.Add(new Jwk(
                    Str(k, "kty") ?? "",
                    Str(k, "kid") ?? "",
                    Str(k, "alg"),
                    Str(k, "use"),
                    Str(k, "n"),
                    Str(k, "e")));
            }
            _lock.EnterWriteLock();
            try { _jwks = new Jwks(keys); }
            finally { _lock.ExitWriteLock(); }
        }
        catch (Exception e)
        {
            throw new IdentityException($"JWKS parse failed: {e.Message}", e);
        }
    }

    /// <summary>
    /// Verify <paramref name="token"/> against the cached JWKS and validate claims.
    /// Returns the verified claims as a <see cref="JsonObject"/>.
    /// </summary>
    public JsonObject Verify(string token)
    {
        Jwks? j;
        _lock.EnterReadLock();
        try { j = _jwks; }
        finally { _lock.ExitReadLock(); }
        if (j is null)
            throw new IdentityException("oidc: JWKS not loaded; call SetJwksFromBytes() first");

        var parts = token.Split('.');
        if (parts.Length != 3) throw new IdentityException("oidc: malformed JWT");

        JsonObject header, claims;
        byte[] signature;
        try
        {
            header = JsonNode.Parse(B64UrlDecode(parts[0]))!.AsObject();
            claims = JsonNode.Parse(B64UrlDecode(parts[1]))!.AsObject();
            signature = B64UrlDecode(parts[2]);
        }
        catch (Exception e)
        {
            throw new IdentityException("oidc: malformed JWT", e);
        }

        string alg = header["alg"]?.GetValue<string>() ?? "";
        if (!_cfg.AllowedAlgorithms.Contains(alg))
            throw new IdentityException($"oidc: algorithm not allowed: {alg}");
        string kid = header["kid"]?.GetValue<string>() ?? "";

        Jwk? match = null;
        foreach (var k in j.Keys)
            if (!string.IsNullOrEmpty(k.Kid) && k.Kid == kid) { match = k; break; }
        if (match is null && j.Keys.Count == 1 && string.IsNullOrEmpty(kid))
            match = j.Keys[0];
        if (match is null)
            throw new IdentityException($"oidc: kid {kid} not found in JWKS");
        if (match.Kty != "RSA")
            throw new IdentityException($"oidc: unsupported key type: {match.Kty}");

        try
        {
            byte[] modulus = B64UrlDecode(match.N!);
            byte[] exponent = B64UrlDecode(match.E!);
            using var rsa = RSA.Create();
            rsa.ImportParameters(new RSAParameters { Modulus = modulus, Exponent = exponent });
            byte[] data = Encoding.UTF8.GetBytes(parts[0] + "." + parts[1]);
            if (!rsa.VerifyData(data, signature, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1))
                throw new IdentityException("oidc: signature verification failed");
        }
        catch (IdentityException) { throw; }
        catch (Exception e)
        {
            throw new IdentityException($"oidc: signature verification error: {e.Message}", e);
        }

        // Issuer check
        if (!string.IsNullOrEmpty(_cfg.Issuer))
        {
            string iss = claims["iss"]?.GetValue<string>() ?? "";
            if (iss != _cfg.Issuer)
                throw new IdentityException($"oidc: iss mismatch: got {iss}, want {_cfg.Issuer}");
        }

        // Expiry check
        if (claims["exp"] is JsonValue ev && ev.TryGetValue<long>(out var exp))
        {
            long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
            if (exp + _cfg.LeewaySeconds < now)
                throw new IdentityException("oidc: token expired");
        }

        // Audience check
        if (!string.IsNullOrEmpty(_cfg.Audience))
        {
            if (!AudienceMatches(claims["aud"], _cfg.Audience))
                throw new IdentityException($"oidc: aud mismatch (expected {_cfg.Audience})");
        }
        return claims;
    }

    private static bool AudienceMatches(JsonNode? aud, string want)
    {
        if (aud is null) return false;
        if (aud is JsonValue v && v.TryGetValue<string>(out var s)) return s == want;
        if (aud is JsonArray arr)
        {
            foreach (var n in arr)
                if (n is JsonValue jv && jv.TryGetValue<string>(out var x) && x == want) return true;
        }
        return false;
    }

    private static string? Str(JsonObject o, string key) =>
        o[key] is JsonValue v && v.TryGetValue<string>(out var s) ? s : null;

    private static byte[] B64UrlDecode(string s)
    {
        s = s.Replace('-', '+').Replace('_', '/');
        switch (s.Length % 4)
        {
            case 2: s += "=="; break;
            case 3: s += "="; break;
        }
        return Convert.FromBase64String(s);
    }

    /// <summary>Convert verified claims into a deduplicated list of IAIso scopes.</summary>
    public static List<string> DeriveScopes(JsonObject claims, ScopeMapping mapping)
    {
        IReadOnlyList<string> directClaims = mapping.DirectClaims.Count == 0
            ? new[] { "scp", "scope", "permissions" }
            : mapping.DirectClaims;

        var seen = new List<string>();
        var seenSet = new HashSet<string>();
        void Add(string s) { if (seenSet.Add(s)) seen.Add(s); }

        foreach (var c in directClaims)
        {
            if (claims[c] is null) continue;
            var node = claims[c];
            if (node is JsonValue v && v.TryGetValue<string>(out var ss))
            {
                foreach (var tok in ss.Split(new[] { ' ', '\t', ',' }, StringSplitOptions.RemoveEmptyEntries))
                    Add(tok);
            }
            else if (node is JsonArray arr)
            {
                foreach (var n in arr)
                    if (n is JsonValue nv && nv.TryGetValue<string>(out var t)) Add(t);
            }
        }

        var groups = new List<string>();
        foreach (var c in new[] { "groups", "roles" })
        {
            if (claims[c] is JsonArray arr)
                foreach (var n in arr)
                    if (n is JsonValue gv && gv.TryGetValue<string>(out var g)) groups.Add(g);
        }
        foreach (var g in groups)
        {
            if (mapping.GroupToScopes.TryGetValue(g, out var mapped))
                foreach (var s in mapped) Add(s);
        }
        foreach (var s in mapping.AlwaysGrant) Add(s);
        return seen;
    }

    /// <summary>Mint an IAIso consent scope from a verified OIDC identity.</summary>
    public static Scope IssueFromOidc(OidcVerifier verifier, Issuer issuer,
                                      string token, ScopeMapping mapping,
                                      long ttlSeconds, string? executionId)
    {
        var claims = verifier.Verify(token);
        string subject = claims["sub"]?.GetValue<string>() ?? "unknown";
        var scopes = DeriveScopes(claims, mapping);

        var metadata = new JsonObject();
        if (claims["iss"] is JsonNode iss) metadata["oidc_iss"] = JsonNode.Parse(iss.ToJsonString());
        if (claims["jti"] is JsonNode jti) metadata["oidc_jti"] = JsonNode.Parse(jti.ToJsonString());
        if (claims["aud"] is JsonNode aud) metadata["oidc_aud"] = JsonNode.Parse(aud.ToJsonString());

        return issuer.Issue(subject, scopes, executionId, ttlSeconds,
            metadata.Count > 0 ? metadata : null);
    }
}
