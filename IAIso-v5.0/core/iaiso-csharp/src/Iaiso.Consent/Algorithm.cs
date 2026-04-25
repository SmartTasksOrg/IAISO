using System;

namespace Iaiso.Consent;

/// <summary>Supported JWT signing algorithms. <c>none</c> is intentionally absent.</summary>
public enum Algorithm
{
    HS256,
    RS256,
}

public static class AlgorithmExtensions
{
    public static string Wire(this Algorithm a) => a switch
    {
        Algorithm.HS256 => "HS256",
        Algorithm.RS256 => "RS256",
        _ => a.ToString(),
    };

    public static Algorithm ParseAlgorithm(string s) => s switch
    {
        "HS256" => Algorithm.HS256,
        "RS256" => Algorithm.RS256,
        _ => throw new ArgumentException($"unsupported algorithm: {s}"),
    };
}

/// <summary>Base type for consent verification failures.</summary>
public abstract class ConsentException : Exception
{
    protected ConsentException(string message) : base(message) {}
    protected ConsentException(string message, Exception inner) : base(message, inner) {}
}

/// <summary>The JWT failed signature, format, or claim validation.</summary>
public sealed class InvalidTokenException : ConsentException
{
    public InvalidTokenException(string message) : base(message) {}
    public InvalidTokenException(string message, Exception inner) : base(message, inner) {}
}

/// <summary>The token's <c>exp</c> claim is in the past (after leeway).</summary>
public sealed class ExpiredTokenException : ConsentException
{
    public ExpiredTokenException() : base("expired token") {}
}

/// <summary>The token's <c>jti</c> is on the revocation list.</summary>
public sealed class RevokedTokenException : ConsentException
{
    public string Jti { get; }
    public RevokedTokenException(string jti) : base($"revoked token: jti={jti}") { Jti = jti; }
}

/// <summary>Thrown when a scope check fails.</summary>
public sealed class InsufficientScopeException : Exception
{
    public IReadOnlyList<string> Granted { get; }
    public string Requested { get; }
    public InsufficientScopeException(IReadOnlyList<string> granted, string requested)
        : base($"scope {requested} not granted by token (granted: {string.Join(", ", granted)})")
    {
        Granted = granted;
        Requested = requested;
    }
}
