using System.Collections.Generic;
using System.Text.Json.Nodes;
using Iaiso.Identity;

namespace Iaiso.Tests;

public sealed class IdentityTests
{
    public void TestDeriveDirectClaimString()
    {
        var claims = JsonNode.Parse("{\"scope\": \"tools.search tools.fetch\"}")!.AsObject();
        var @out = OidcVerifier.DeriveScopes(claims, ScopeMapping.Defaults());
        Assert.True(@out.Contains("tools.search"));
        Assert.True(@out.Contains("tools.fetch"));
    }

    public void TestDeriveDirectClaimArray()
    {
        var claims = JsonNode.Parse("{\"scp\": [\"a.b\", \"c\"]}")!.AsObject();
        var @out = OidcVerifier.DeriveScopes(claims, ScopeMapping.Defaults());
        Assert.SequenceEqual(new[] { "a.b", "c" }, @out);
    }

    public void TestDeriveGroupToScopes()
    {
        var claims = JsonNode.Parse("{\"groups\": [\"engineers\"]}")!.AsObject();
        var g = new Dictionary<string, IReadOnlyList<string>>
        {
            ["engineers"] = new[] { "tools.search", "tools.fetch" },
        };
        var mapping = new ScopeMapping(new List<string>(), g, null);
        var @out = OidcVerifier.DeriveScopes(claims, mapping);
        Assert.True(@out.Contains("tools.search"));
        Assert.True(@out.Contains("tools.fetch"));
    }

    public void TestAlwaysGrantAdded()
    {
        var claims = new JsonObject();
        var mapping = new ScopeMapping(new List<string>(), null, new[] { "base" });
        Assert.SequenceEqual(new[] { "base" }, OidcVerifier.DeriveScopes(claims, mapping));
    }

    public void TestPresetsHaveExpectedEndpoints()
    {
        var okta = ProviderConfig.Okta("acme.okta.com", "api");
        Assert.Contains("acme.okta.com", okta.DiscoveryUrl!);
        var auth0 = ProviderConfig.Auth0("acme.auth0.com", "api");
        Assert.True(auth0.Issuer!.EndsWith("/"));
        var azureV2 = ProviderConfig.AzureAd("tenant-id", "api", true);
        Assert.Contains("v2.0", azureV2.DiscoveryUrl!);
    }

    public void TestVerifyFailsWhenJwksNotLoaded()
    {
        var v = new OidcVerifier(ProviderConfig.Defaults());
        Assert.Throws<IdentityException>(() => v.Verify("a.b.c"));
    }
}
