using System;
using System.Collections.Generic;

namespace Iaiso.Consent;

/// <summary>
/// Scope grammar and matching, per <c>spec/consent/README.md §4–§5</c>.
/// </summary>
/// <remarks>
/// <code>
/// scope   ::= segment ("." segment)*
/// segment ::= [a-z0-9_-]+
/// </code>
/// A token granting <c>G</c> satisfies a request for <c>R</c> iff:
/// <list type="bullet">
///   <item><c>G == R</c> (exact match), or</item>
///   <item><c>R</c> starts with <c>G + "."</c> (prefix at segment boundary).</item>
/// </list>
/// </remarks>
public static class Scopes
{
    public static bool Granted(IReadOnlyList<string> granted, string requested)
    {
        if (string.IsNullOrEmpty(requested))
        {
            throw new ArgumentException("requested scope must be non-empty", nameof(requested));
        }
        foreach (var g in granted)
        {
            if (g == requested) return true;
            if (requested.StartsWith(g + ".", StringComparison.Ordinal)) return true;
        }
        return false;
    }
}
