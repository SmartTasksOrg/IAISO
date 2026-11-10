using System;
using System.Collections.Generic;
using System.Linq;
using System.Reflection;

namespace Iaiso.Tests;

/// <summary>
/// Minimal assertion helper. Throws <see cref="AssertionException"/>
/// on failure so the test runner can pick it up.
/// </summary>
public static class Assert
{
    public static void True(bool condition, string? message = null)
    {
        if (!condition) throw new AssertionException(message ?? "expected true");
    }

    public static void False(bool condition, string? message = null)
    {
        if (condition) throw new AssertionException(message ?? "expected false");
    }

    public static void Null(object? value, string? message = null)
    {
        if (value is not null) throw new AssertionException(message ?? $"expected null, got {value}");
    }

    public static void NotNull(object? value, string? message = null)
    {
        if (value is null) throw new AssertionException(message ?? "expected non-null");
    }

    public static void Equal<T>(T expected, T actual, string? message = null)
    {
        if (!EqualityComparer<T>.Default.Equals(expected, actual))
            throw new AssertionException(message ?? $"expected {expected}, got {actual}");
    }

    public static void EqualDouble(double expected, double actual, double tolerance = 1e-9, string? message = null)
    {
        if (Math.Abs(expected - actual) > tolerance)
            throw new AssertionException(message ?? $"expected {expected}, got {actual} (tolerance {tolerance})");
    }

    public static void Throws<T>(Action action, string? message = null) where T : Exception
    {
        try
        {
            action();
        }
        catch (T) { return; }
        catch (Exception e)
        {
            throw new AssertionException(message ?? $"expected {typeof(T).Name}, got {e.GetType().Name}: {e.Message}");
        }
        throw new AssertionException(message ?? $"expected {typeof(T).Name}, got no exception");
    }

    public static void Contains(string substring, string actual, string? message = null)
    {
        if (!actual.Contains(substring))
            throw new AssertionException(message ?? $"expected '{actual}' to contain '{substring}'");
    }

    public static void SequenceEqual<T>(IEnumerable<T> expected, IEnumerable<T> actual, string? message = null)
    {
        if (!expected.SequenceEqual(actual))
            throw new AssertionException(message ?? "sequences differ");
    }
}

public sealed class AssertionException : Exception
{
    public AssertionException(string message) : base(message) {}
}

/// <summary>
/// In-tree test runner. Discovers test classes via reflection (any
/// class ending in <c>Tests</c>) and runs all public methods whose
/// name begins with <c>Test</c>. Returns nonzero exit code on failure.
/// </summary>
public static class TestRunner
{
    public static int Run(Assembly asm)
    {
        var classes = asm.GetTypes()
            .Where(t => t.IsClass && t.IsPublic && t.Name.EndsWith("Tests"))
            .OrderBy(t => t.FullName, StringComparer.Ordinal)
            .ToArray();

        int total = 0, passed = 0;
        var failures = new List<string>();
        Console.WriteLine($"running {classes.Length} test class(es)...");
        foreach (var cls in classes)
        {
            var methods = cls.GetMethods(BindingFlags.Public | BindingFlags.Instance)
                .Where(m => m.Name.StartsWith("Test") && m.GetParameters().Length == 0)
                .OrderBy(m => m.Name, StringComparer.Ordinal)
                .ToArray();
            if (methods.Length == 0) continue;

            object? instance = null;
            try { instance = Activator.CreateInstance(cls); }
            catch (Exception e)
            {
                Console.WriteLine($"  [{cls.Name}] failed to construct: {e.InnerException?.Message ?? e.Message}");
                failures.Add(cls.Name);
                continue;
            }

            foreach (var m in methods)
            {
                total++;
                try
                {
                    m.Invoke(instance, null);
                    passed++;
                    Console.Write(".");
                }
                catch (TargetInvocationException tie)
                {
                    Console.Write("F");
                    var inner = tie.InnerException ?? tie;
                    failures.Add($"{cls.Name}.{m.Name}: {inner.GetType().Name}: {inner.Message}");
                }
                catch (Exception e)
                {
                    Console.Write("F");
                    failures.Add($"{cls.Name}.{m.Name}: {e.GetType().Name}: {e.Message}");
                }
            }
        }
        Console.WriteLine();
        Console.WriteLine();
        if (failures.Count > 0)
        {
            Console.WriteLine($"{failures.Count} failure(s):");
            foreach (var f in failures) Console.WriteLine($"  {f}");
            Console.WriteLine();
        }
        Console.WriteLine($"tests: {passed}/{total} passed");
        return failures.Count > 0 ? 1 : 0;
    }
}
