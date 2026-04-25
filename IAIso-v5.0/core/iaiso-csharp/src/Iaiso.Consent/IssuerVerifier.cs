using System;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Text.Json.Nodes;

namespace Iaiso.Consent;

/// <summary>A clock returning UNIX seconds.</summary>
public delegate long SecondsClock();

internal static class SecondsClocks
{
    public static long Wallclock() => DateTimeOffset.UtcNow.ToUnixTimeSeconds();
}

/// <summary>Mints signed consent tokens.</summary>
public sealed class Issuer
{
    private readonly byte[]? _hsKey;
    private readonly RSA? _rsKey;
    private readonly Algorithm _algorithm;
    private readonly string _issuer;
    private readonly long _defaultTtlSeconds;
    private readonly SecondsClock _clock;
    private readonly RandomNumberGenerator _rng = RandomNumberGenerator.Create();

    private Issuer(Builder b)
    {
        _hsKey = b.HsKey;
        _rsKey = b.RsKey;
        _algorithm = b.Algorithm;
        _issuer = b.Issuer;
        _defaultTtlSeconds = b.DefaultTtlSeconds;
        _clock = b.Clock ?? SecondsClocks.Wallclock;
    }

    public static Builder CreateBuilder() => new();

    /// <summary>Issue a token.</summary>
    public Scope Issue(string subject, IReadOnlyList<string> scopes, string? executionId,
                       long? ttlSeconds, JsonObject? metadata)
    {
        long now = _clock();
        long ttl = ttlSeconds ?? _defaultTtlSeconds;
        long exp = now + ttl;
        string jti = GenerateJti();

        var claims = new JsonObject
        {
            ["iss"] = _issuer,
            ["sub"] = subject,
            ["iat"] = now,
            ["exp"] = exp,
            ["jti"] = jti,
        };
        var scopesArr = new JsonArray();
        foreach (var s in scopes) scopesArr.Add(s);
        claims["scopes"] = scopesArr;
        if (!string.IsNullOrEmpty(executionId)) claims["execution_id"] = executionId;
        if (metadata is not null && metadata.Count > 0) claims["metadata"] = JsonNode.Parse(metadata.ToJsonString());

        string token = Jwt.Sign(_algorithm, claims, _hsKey, _rsKey);

        return new Scope(token, subject, new List<string>(scopes),
            executionId, jti, now, exp,
            metadata is null ? new JsonObject() : (JsonObject)JsonNode.Parse(metadata.ToJsonString())!);
    }

    /// <summary>Generate a 64-byte base64url-without-padding HS256 secret.</summary>
    public static string GenerateHs256Secret()
    {
        var buf = new byte[64];
        using var rng = RandomNumberGenerator.Create();
        rng.GetBytes(buf);
        return Jwt.B64Url(buf);
    }

    private string GenerateJti()
    {
        var buf = new byte[16];
        _rng.GetBytes(buf);
        return Convert.ToHexString(buf).ToLowerInvariant();
    }

    public sealed class Builder
    {
        public byte[]? HsKey { get; set; }
        public RSA? RsKey { get; set; }
        public Algorithm Algorithm { get; set; } = Algorithm.HS256;
        public string Issuer { get; set; } = "iaiso";
        public long DefaultTtlSeconds { get; set; } = 3600;
        public SecondsClock? Clock { get; set; }

        public Builder WithHsKey(byte[] v) { HsKey = v; return this; }
        public Builder WithRsKey(RSA v) { RsKey = v; return this; }
        public Builder WithAlgorithm(Algorithm v) { Algorithm = v; return this; }
        public Builder WithIssuer(string v) { Issuer = v; return this; }
        public Builder WithDefaultTtlSeconds(long v) { DefaultTtlSeconds = v; return this; }
        public Builder WithClock(SecondsClock v) { Clock = v; return this; }

        public Issuer Build() => new(this);
    }
}

/// <summary>Verifies signed consent tokens.</summary>
public sealed class Verifier
{
    private readonly byte[]? _hsKey;
    private readonly RSA? _rsKey;
    private readonly Algorithm _algorithm;
    private readonly string _issuer;
    private readonly RevocationList? _revocationList;
    private readonly long _leewaySeconds;
    private readonly SecondsClock _clock;

    private Verifier(Builder b)
    {
        _hsKey = b.HsKey;
        _rsKey = b.RsKey;
        _algorithm = b.Algorithm;
        _issuer = b.Issuer;
        _revocationList = b.RevocationList;
        _leewaySeconds = b.LeewaySeconds;
        _clock = b.Clock ?? SecondsClocks.Wallclock;
    }

    public static Builder CreateBuilder() => new();

    /// <summary>
    /// Verify <paramref name="token"/>. If <paramref name="requestedExecutionId"/>
    /// is non-null and the token is bound to a different execution, throws
    /// <see cref="InvalidTokenException"/>.
    /// </summary>
    public Scope Verify(string token, string? requestedExecutionId)
    {
        var parsed = Jwt.Parse(token);

        // Algorithm check from header
        var algNode = parsed.Header["alg"];
        string headerAlg = algNode?.GetValue<string>() ?? "";
        if (headerAlg != _algorithm.Wire())
        {
            throw new InvalidTokenException(
                $"unexpected algorithm: {(string.IsNullOrEmpty(headerAlg) ? "missing" : headerAlg)}");
        }

        // Signature check
        if (!Jwt.VerifySignature(parsed, _algorithm, _hsKey, _rsKey))
        {
            throw new InvalidTokenException("signature verification failed");
        }

        var claims = parsed.Claims;

        // Required claims
        foreach (var required in new[] { "exp", "iat", "iss", "sub", "jti" })
        {
            if (claims[required] is null)
            {
                throw new InvalidTokenException($"missing required claim: {required}");
            }
        }

        // Issuer
        string issClaim = claims["iss"]!.GetValue<string>();
        if (issClaim != _issuer)
        {
            throw new InvalidTokenException($"iss mismatch: got {issClaim}, want {_issuer}");
        }

        // Expiry
        long exp = claims["exp"]!.GetValue<long>();
        long now = _clock();
        if (exp + _leewaySeconds < now)
        {
            throw new ExpiredTokenException();
        }

        // Revocation
        string jti = claims["jti"]!.GetValue<string>();
        if (_revocationList is not null && _revocationList.IsRevoked(jti))
        {
            throw new RevokedTokenException(jti);
        }

        // Execution binding
        string? tokenExec = claims["execution_id"]?.GetValue<string>();
        if (requestedExecutionId is not null && tokenExec is not null
            && requestedExecutionId != tokenExec)
        {
            throw new InvalidTokenException(
                $"token bound to {tokenExec}, requested {requestedExecutionId}");
        }

        // Build Scope
        string subject = claims["sub"]!.GetValue<string>();
        long iat = claims["iat"]!.GetValue<long>();
        var scopes = new List<string>();
        if (claims["scopes"] is JsonArray arr)
        {
            foreach (var node in arr)
            {
                if (node is not null) scopes.Add(node.GetValue<string>());
            }
        }
        var metadata = claims["metadata"] is JsonObject mo
            ? (JsonObject)JsonNode.Parse(mo.ToJsonString())!
            : new JsonObject();

        return new Scope(token, subject, scopes, tokenExec, jti, iat, exp, metadata);
    }

    public sealed class Builder
    {
        public byte[]? HsKey { get; set; }
        public RSA? RsKey { get; set; }
        public Algorithm Algorithm { get; set; } = Algorithm.HS256;
        public string Issuer { get; set; } = "iaiso";
        public RevocationList? RevocationList { get; set; }
        public long LeewaySeconds { get; set; } = 5;
        public SecondsClock? Clock { get; set; }

        public Builder WithHsKey(byte[] v) { HsKey = v; return this; }
        public Builder WithRsKey(RSA v) { RsKey = v; return this; }
        public Builder WithAlgorithm(Algorithm v) { Algorithm = v; return this; }
        public Builder WithIssuer(string v) { Issuer = v; return this; }
        public Builder WithRevocationList(RevocationList v) { RevocationList = v; return this; }
        public Builder WithLeewaySeconds(long v) { LeewaySeconds = v; return this; }
        public Builder WithClock(SecondsClock v) { Clock = v; return this; }

        public Verifier Build() => new(this);
    }
}
