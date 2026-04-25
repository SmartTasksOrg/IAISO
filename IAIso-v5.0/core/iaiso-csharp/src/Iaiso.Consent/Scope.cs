using System.Collections.Generic;
using System.Text.Json;
using System.Text.Json.Nodes;
using System.Threading;

namespace Iaiso.Consent;

/// <summary>A verified consent scope, ready to attach to an execution.</summary>
public sealed class Scope
{
    public string Token { get; }
    public string Subject { get; }
    public IReadOnlyList<string> Scopes { get; }
    public string? ExecutionId { get; }
    public string Jti { get; }
    public long IssuedAt { get; }
    public long ExpiresAt { get; }
    public JsonObject Metadata { get; }

    public Scope(string token, string subject, IReadOnlyList<string> scopes,
                 string? executionId, string jti, long issuedAt, long expiresAt,
                 JsonObject? metadata)
    {
        Token = token;
        Subject = subject;
        Scopes = scopes;
        ExecutionId = executionId;
        Jti = jti;
        IssuedAt = issuedAt;
        ExpiresAt = expiresAt;
        Metadata = metadata ?? new JsonObject();
    }

    public bool Grants(string requested) => Iaiso.Consent.Scopes.Granted(Scopes, requested);

    public void Require(string requested)
    {
        if (!Grants(requested))
        {
            throw new InsufficientScopeException(Scopes, requested);
        }
    }
}

/// <summary>
/// In-memory revocation list. Production deployments should back this
/// with Redis, a database, or similar.
/// </summary>
public sealed class RevocationList
{
    private readonly HashSet<string> _revoked = new();
    private readonly ReaderWriterLockSlim _lock = new();

    public void Revoke(string jti)
    {
        _lock.EnterWriteLock();
        try { _revoked.Add(jti); }
        finally { _lock.ExitWriteLock(); }
    }

    public bool IsRevoked(string jti)
    {
        _lock.EnterReadLock();
        try { return _revoked.Contains(jti); }
        finally { _lock.ExitReadLock(); }
    }

    public int Count
    {
        get
        {
            _lock.EnterReadLock();
            try { return _revoked.Count; }
            finally { _lock.ExitReadLock(); }
        }
    }

    public IReadOnlySet<string> Snapshot()
    {
        _lock.EnterReadLock();
        try { return new HashSet<string>(_revoked); }
        finally { _lock.ExitReadLock(); }
    }
}
