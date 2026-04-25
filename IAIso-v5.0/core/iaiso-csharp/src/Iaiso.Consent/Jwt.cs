using System;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json.Nodes;

namespace Iaiso.Consent;

/// <summary>
/// Minimal JWT codec used by <see cref="Issuer"/> and <see cref="Verifier"/>.
/// Implements just enough of RFC 7519 to support HS256 and RS256 — the
/// spec requirements for IAIso consent. No external library dependency.
/// </summary>
internal static class Jwt
{
    /// <summary>Encode bytes as base64url without padding.</summary>
    public static string B64Url(byte[] data)
    {
        // Convert.ToBase64String -> standard base64; convert to URL-safe and strip padding
        string s = Convert.ToBase64String(data);
        s = s.TrimEnd('=').Replace('+', '-').Replace('/', '_');
        return s;
    }

    public static byte[] B64UrlDecode(string s)
    {
        s = s.Replace('-', '+').Replace('_', '/');
        switch (s.Length % 4)
        {
            case 2: s += "=="; break;
            case 3: s += "="; break;
        }
        return Convert.FromBase64String(s);
    }

    /// <summary>Sign claims and return a compact JWT string.</summary>
    public static string Sign(Algorithm alg, JsonObject claims, byte[]? hsKey, RSA? rsKey)
    {
        var header = new JsonObject
        {
            ["alg"] = alg.Wire(),
            ["typ"] = "JWT",
        };
        string headerB64 = B64Url(Encoding.UTF8.GetBytes(header.ToJsonString()));
        string claimsB64 = B64Url(Encoding.UTF8.GetBytes(claims.ToJsonString()));
        string signingInput = headerB64 + "." + claimsB64;
        byte[] signingBytes = Encoding.UTF8.GetBytes(signingInput);

        byte[] sig = alg switch
        {
            Algorithm.HS256 => HmacSha256(signingBytes, hsKey ?? throw new ArgumentNullException(nameof(hsKey))),
            Algorithm.RS256 => RsaSign(signingBytes, rsKey ?? throw new ArgumentNullException(nameof(rsKey))),
            _ => throw new ArgumentException($"unsupported algorithm: {alg}"),
        };
        return signingInput + "." + B64Url(sig);
    }

    /// <summary>Parsed JWT with raw header, claims, and signature parts.</summary>
    public sealed class Parsed
    {
        public string HeaderB64 { get; }
        public string ClaimsB64 { get; }
        public string SignatureB64 { get; }
        public JsonObject Header { get; }
        public JsonObject Claims { get; }
        public byte[] Signature { get; }

        public Parsed(string h, string c, string s)
        {
            HeaderB64 = h;
            ClaimsB64 = c;
            SignatureB64 = s;
            try
            {
                Header = JsonNode.Parse(Encoding.UTF8.GetString(B64UrlDecode(h)))!.AsObject();
                Claims = JsonNode.Parse(Encoding.UTF8.GetString(B64UrlDecode(c)))!.AsObject();
                Signature = B64UrlDecode(s);
            }
            catch (Exception e)
            {
                throw new InvalidTokenException("malformed JWT", e);
            }
        }

        public string SigningInput() => HeaderB64 + "." + ClaimsB64;
    }

    /// <summary>Parse a compact JWT into header / claims / signature parts.</summary>
    public static Parsed Parse(string token)
    {
        if (token is null) throw new InvalidTokenException("token is null");
        var parts = token.Split('.');
        if (parts.Length != 3)
            throw new InvalidTokenException($"expected 3 JWT parts, got {parts.Length}");
        return new Parsed(parts[0], parts[1], parts[2]);
    }

    /// <summary>Verify the signature on a parsed JWT.</summary>
    public static bool VerifySignature(Parsed parsed, Algorithm alg, byte[]? hsKey, RSA? rsKey)
    {
        byte[] data = Encoding.UTF8.GetBytes(parsed.SigningInput());
        return alg switch
        {
            Algorithm.HS256 => ConstantTimeEquals(HmacSha256(data, hsKey!), parsed.Signature),
            Algorithm.RS256 => RsaVerify(data, parsed.Signature, rsKey!),
            _ => false,
        };
    }

    private static byte[] HmacSha256(byte[] data, byte[] key)
    {
        using var hmac = new HMACSHA256(key);
        return hmac.ComputeHash(data);
    }

    private static byte[] RsaSign(byte[] data, RSA key)
    {
        return key.SignData(data, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
    }

    private static bool RsaVerify(byte[] data, byte[] signature, RSA key)
    {
        try
        {
            return key.VerifyData(data, signature, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
        }
        catch (CryptographicException) { return false; }
    }

    private static bool ConstantTimeEquals(byte[] a, byte[] b)
    {
        if (a is null || b is null || a.Length != b.Length) return false;
        int diff = 0;
        for (int i = 0; i < a.Length; i++) diff |= a[i] ^ b[i];
        return diff == 0;
    }
}
