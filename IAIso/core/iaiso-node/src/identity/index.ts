/**
 * OIDC identity integration.
 *
 * Verify access / ID tokens from Okta, Auth0, Azure AD, or any
 * conforming OIDC provider, then either:
 *
 *   (a) enrich an incoming OIDC token into a ConsentScope directly, or
 *   (b) mint an IAIso-signed ConsentScope via ConsentIssuer using
 *       scopes derived from the OIDC claims.
 *
 * Install:
 *   npm install jose
 *
 * Provider presets are provided for Okta, Auth0, and Azure AD/Entra;
 * the generic `OIDCVerifier` works against any OIDC provider by passing
 * `discoveryUrl` (auto-fetches the JWKS endpoint) or `jwksUrl` directly.
 */

import {
  createRemoteJWKSet,
  jwtVerify,
  type JWTPayload,
} from "jose";

import { ConsentError } from "../consent/errors.js";
import type { ConsentIssuer, ConsentScope } from "../consent/index.js";

// -- Errors -----------------------------------------------------------------

export class OIDCError extends ConsentError {
  constructor(message: string) {
    super(message);
    this.name = "OIDCError";
  }
}

export class OIDCNetworkError extends OIDCError {
  constructor(message: string) {
    super(message);
    this.name = "OIDCNetworkError";
  }
}

// -- Config -----------------------------------------------------------------

export interface OIDCProviderConfig {
  /** `https://<issuer>/.well-known/openid-configuration` */
  discoveryUrl?: string;
  /** Direct JWKS endpoint; overrides discovery. */
  jwksUrl?: string;
  /** Expected `iss` claim. If omitted, trust discovery's issuer. */
  issuer?: string;
  /** Expected `aud` claim. If omitted, audience validation is skipped. */
  audience?: string;
  /** Signing algorithms to accept. Defaults to RS256 + ES256. */
  allowedAlgorithms?: string[];
  /** JWKS cache TTL in seconds. */
  jwksCacheSeconds?: number;
  /** Clock skew tolerance for expiry/nbf. */
  leewaySeconds?: number;
}

export function oktaConfig(
  params: { domain: string; audience?: string } & Partial<OIDCProviderConfig>,
): OIDCProviderConfig {
  const issuer = `https://${params.domain}`;
  return {
    discoveryUrl: `${issuer}/.well-known/openid-configuration`,
    issuer,
    audience: params.audience,
    allowedAlgorithms: ["RS256"],
    ...params,
  };
}

export function auth0Config(
  params: { domain: string; audience?: string } & Partial<OIDCProviderConfig>,
): OIDCProviderConfig {
  const issuer = `https://${params.domain}/`;
  return {
    discoveryUrl: `https://${params.domain}/.well-known/openid-configuration`,
    issuer,
    audience: params.audience,
    allowedAlgorithms: ["RS256"],
    ...params,
  };
}

export function azureAdConfig(
  params: {
    tenant: string;
    audience?: string;
    v2?: boolean;
  } & Partial<OIDCProviderConfig>,
): OIDCProviderConfig {
  const base = params.v2 === false
    ? `https://login.microsoftonline.com/${params.tenant}`
    : `https://login.microsoftonline.com/${params.tenant}/v2.0`;
  return {
    discoveryUrl: `${base}/.well-known/openid-configuration`,
    issuer: base,
    audience: params.audience,
    allowedAlgorithms: ["RS256"],
    ...params,
  };
}

// -- Verifier ---------------------------------------------------------------

interface DiscoveryDocument {
  issuer?: string;
  jwks_uri?: string;
}

/**
 * Verifies OIDC tokens against a provider's JWKS.
 *
 * JWKS fetches are cached by `jose.createRemoteJWKSet`. Discovery
 * documents are fetched once and cached for the lifetime of the
 * verifier.
 */
export class OIDCVerifier {
  readonly config: OIDCProviderConfig;
  private _jwks: ReturnType<typeof createRemoteJWKSet> | null = null;
  private _resolvedIssuer: string | null = null;
  private _discoveryPromise: Promise<void> | null = null;

  constructor(config: OIDCProviderConfig) {
    if (!config.discoveryUrl && !config.jwksUrl) {
      throw new OIDCError(
        "OIDCProviderConfig requires either discoveryUrl or jwksUrl",
      );
    }
    this.config = {
      allowedAlgorithms: ["RS256", "ES256"],
      jwksCacheSeconds: 600,
      leewaySeconds: 5,
      ...config,
    };
  }

  private async _ensureDiscovery(): Promise<void> {
    if (this._jwks) return;
    if (this._discoveryPromise) {
      await this._discoveryPromise;
      return;
    }
    this._discoveryPromise = (async () => {
      let jwksUrl = this.config.jwksUrl;
      let resolvedIssuer = this.config.issuer ?? null;

      if (!jwksUrl && this.config.discoveryUrl) {
        let resp: Response;
        try {
          resp = await fetch(this.config.discoveryUrl);
        } catch (err) {
          throw new OIDCNetworkError(
            `discovery failed: ${(err as Error).message}`,
          );
        }
        if (!resp.ok) {
          throw new OIDCNetworkError(
            `discovery returned HTTP ${resp.status}`,
          );
        }
        const doc = (await resp.json()) as DiscoveryDocument;
        jwksUrl = doc.jwks_uri;
        resolvedIssuer = resolvedIssuer ?? doc.issuer ?? null;
      }

      if (!jwksUrl) {
        throw new OIDCError("no JWKS URL resolved from config or discovery");
      }

      this._jwks = createRemoteJWKSet(new URL(jwksUrl), {
        cacheMaxAge: (this.config.jwksCacheSeconds ?? 600) * 1000,
      });
      this._resolvedIssuer = resolvedIssuer;
    })();
    await this._discoveryPromise;
  }

  /**
   * Verify an OIDC token and return its validated claims.
   * Throws OIDCError on any failure.
   */
  async verify(token: string): Promise<JWTPayload> {
    await this._ensureDiscovery();
    if (!this._jwks) {
      throw new OIDCError("JWKS not initialized");
    }

    try {
      const { payload } = await jwtVerify(
        token,
        this._jwks as unknown as Parameters<typeof jwtVerify>[1],
        {
          algorithms: this.config.allowedAlgorithms,
          issuer: this.config.issuer ?? this._resolvedIssuer ?? undefined,
          audience: this.config.audience,
          clockTolerance: this.config.leewaySeconds,
        },
      );
      return payload;
    } catch (err) {
      throw new OIDCError(
        `OIDC verification failed: ${(err as Error).message}`,
      );
    }
  }
}

// -- Scope mapping ---------------------------------------------------------

export interface ScopeMapping {
  /** OIDC claims that carry scope-like strings (e.g. `scp`, `scope`, `permissions`). */
  directClaims?: string[];
  /** Group → scope mappings. Each group in `groups`/`roles` maps to the
   *  listed scopes. */
  groupToScopes?: Record<string, string[]>;
  /** Unconditional scopes added to every derived scope list. */
  alwaysGrant?: string[];
}

/**
 * Derive an IAIso scope list from OIDC claims according to the mapping.
 */
export function deriveScopes(
  claims: JWTPayload,
  mapping: ScopeMapping = {},
): string[] {
  const scopes = new Set<string>();

  const directClaims = mapping.directClaims ?? ["scp", "scope", "permissions"];
  for (const c of directClaims) {
    const raw = claims[c];
    if (typeof raw === "string") {
      // Space- or comma-separated
      for (const s of raw.split(/[\s,]+/).filter(Boolean)) scopes.add(s);
    } else if (Array.isArray(raw)) {
      for (const s of raw) {
        if (typeof s === "string") scopes.add(s);
      }
    }
  }

  if (mapping.groupToScopes) {
    const groups: string[] = [];
    for (const claim of ["groups", "roles"]) {
      const v = claims[claim];
      if (Array.isArray(v)) {
        for (const g of v) if (typeof g === "string") groups.push(g);
      }
    }
    for (const g of groups) {
      const mapped = mapping.groupToScopes[g];
      if (mapped) {
        for (const s of mapped) scopes.add(s);
      }
    }
  }

  for (const s of mapping.alwaysGrant ?? []) scopes.add(s);

  return Array.from(scopes);
}

// -- High-level flows ------------------------------------------------------

/**
 * Enrich an OIDC-verified claim set into a ConsentScope by minting an
 * IAIso-signed token locally. Use this when you trust the OIDC provider
 * for authentication but want IAIso-native scope semantics and
 * revocation support.
 */
export async function issueFromOidc(params: {
  verifier: OIDCVerifier;
  issuer: ConsentIssuer;
  token: string;
  mapping?: ScopeMapping;
  ttlSeconds?: number;
  executionId?: string;
}): Promise<ConsentScope> {
  const claims = await params.verifier.verify(params.token);
  const subject = String(claims.sub ?? "unknown");
  const scopes = deriveScopes(claims, params.mapping);
  return params.issuer.issue({
    subject,
    scopes,
    ttl_seconds: params.ttlSeconds,
    execution_id: params.executionId,
    metadata: {
      oidc_iss: claims.iss,
      oidc_jti: claims.jti,
      oidc_aud: claims.aud,
    },
  });
}
