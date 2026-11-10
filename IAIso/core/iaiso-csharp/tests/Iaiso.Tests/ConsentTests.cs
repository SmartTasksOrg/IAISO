using System.Text;
using Iaiso.Consent;

namespace Iaiso.Tests;

public sealed class ConsentTests
{
    private static readonly byte[] Secret =
        Encoding.UTF8.GetBytes("test_secret_long_enough_for_hs256_security_xx");

    public void TestScopeExactMatch()
    {
        Assert.True(Scopes.Granted(new[] { "tools.search" }, "tools.search"));
    }

    public void TestScopePrefixAtBoundary()
    {
        Assert.True(Scopes.Granted(new[] { "tools" }, "tools.search"));
    }

    public void TestScopeSubstringNotBoundary()
    {
        Assert.False(Scopes.Granted(new[] { "tools" }, "toolsbar"));
    }

    public void TestScopeMoreSpecificDoesntSatisfyLessSpecific()
    {
        Assert.False(Scopes.Granted(new[] { "tools.search.bulk" }, "tools.search"));
    }

    public void TestScopeEmptyRequestedThrows()
    {
        Assert.Throws<System.ArgumentException>(() =>
            Scopes.Granted(new[] { "tools" }, ""));
    }

    public void TestIssueVerifyRoundtrip()
    {
        var issuer = Issuer.CreateBuilder()
            .WithHsKey(Secret)
            .WithAlgorithm(Algorithm.HS256)
            .WithIssuer("iaiso")
            .WithClock(() => 1_700_000_000L)
            .Build();
        var scope = issuer.Issue("user-1",
            new[] { "tools.search", "tools.fetch" },
            null, 3600L, null);
        Assert.NotNull(scope.Token);

        var verifier = Verifier.CreateBuilder()
            .WithHsKey(Secret)
            .WithAlgorithm(Algorithm.HS256)
            .WithIssuer("iaiso")
            .WithClock(() => 1_700_000_001L)
            .Build();
        var verified = verifier.Verify(scope.Token, null);
        Assert.Equal("user-1", verified.Subject);
        Assert.True(verified.Grants("tools.search"));
    }

    public void TestVerifyRejectsExpired()
    {
        var issuer = Issuer.CreateBuilder()
            .WithHsKey(Secret)
            .WithClock(() => 1_700_000_000L)
            .Build();
        var scope = issuer.Issue("u", new[] { "tools" }, null, 1L, null);

        var verifier = Verifier.CreateBuilder()
            .WithHsKey(Secret)
            .WithClock(() => 1_700_000_010L)  // 10s past exp
            .Build();
        Assert.Throws<ExpiredTokenException>(() => verifier.Verify(scope.Token, null));
    }

    public void TestVerifyHonorsRevocation()
    {
        var issuer = Issuer.CreateBuilder()
            .WithHsKey(Secret)
            .WithClock(() => 1_700_000_000L)
            .Build();
        var scope = issuer.Issue("u", new[] { "tools" }, null, 3600L, null);
        var rl = new RevocationList();
        rl.Revoke(scope.Jti);

        var verifier = Verifier.CreateBuilder()
            .WithHsKey(Secret)
            .WithRevocationList(rl)
            .WithClock(() => 1_700_000_001L)
            .Build();
        Assert.Throws<RevokedTokenException>(() => verifier.Verify(scope.Token, null));
    }

    public void TestVerifyHonorsExecutionBinding()
    {
        var issuer = Issuer.CreateBuilder()
            .WithHsKey(Secret)
            .WithClock(() => 1_700_000_000L)
            .Build();
        var scope = issuer.Issue("u", new[] { "tools" }, "exec-abc", 3600L, null);

        var verifier = Verifier.CreateBuilder()
            .WithHsKey(Secret)
            .WithClock(() => 1_700_000_001L)
            .Build();
        Assert.Throws<InvalidTokenException>(() => verifier.Verify(scope.Token, "exec-xyz"));
    }

    public void TestVerifyRejectsTamperedToken()
    {
        var issuer = Issuer.CreateBuilder()
            .WithHsKey(Secret)
            .WithClock(() => 1_700_000_000L)
            .Build();
        var scope = issuer.Issue("u", new[] { "tools" }, null, 3600L, null);
        // Flip characters in the signature part
        string tampered = scope.Token[..^5] + "XXXXX";

        var verifier = Verifier.CreateBuilder()
            .WithHsKey(Secret)
            .WithClock(() => 1_700_000_001L)
            .Build();
        Assert.Throws<InvalidTokenException>(() => verifier.Verify(tampered, null));
    }

    public void TestGenerateHs256SecretIsLongEnough()
    {
        var s = Issuer.GenerateHs256Secret();
        Assert.True(s.Length >= 64, $"generated secret too short: {s.Length}");
    }
}
