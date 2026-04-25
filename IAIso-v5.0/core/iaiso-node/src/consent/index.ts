/**
 * ConsentScope — signed, time-bounded, scope-limited authorization tokens.
 *
 * Port of iaiso.consent from the Python reference. See
 * spec/consent/README.md for the normative specification and
 * spec/consent/vectors.json for the 23 conformance vectors this module
 * must pass.
 *
 * Scope grammar (spec §4):
 *   scope   ::= segment ("." segment)*
 *   segment ::= [a-z0-9_-]+
 *
 * A token granting `G` satisfies a request for `R` iff:
 *   - G === R (exact match), OR
 *   - R starts with G + "." (prefix at segment boundary).
 *
 * Supported algorithms: HS256 (default) and RS256. The verifier MUST reject
 * `alg=none` regardless of how it's configured.
 */

import jwt from "jsonwebtoken";
import { randomUUID } from "node:crypto";

import {
  ConsentError,
  ExpiredToken,
  InsufficientScope,
  InvalidToken,
  RevokedToken,
} from "./errors.js";

export type Algorithm = "HS256" | "RS256";

/**
 * Check whether the list of granted scopes satisfies a request.
 * See spec/consent/README.md §5.
 */
export function scopeGranted(granted: string[], requested: string): boolean {
  if (!requested || requested.length === 0) {
    throw new Error("requested scope must be non-empty");
  }
  for (const g of granted) {
    if (g === requested) return true;
    if (requested.startsWith(g + ".")) return true;
  }
  return false;
}

/**
 * A verified consent token ready to be attached to an execution.
 */
export class ConsentScope {
  readonly token: string;
  readonly subject: string;
  readonly scopes: string[];
  readonly execution_id: string | null;
  readonly jti: string;
  readonly issued_at: number;
  readonly expires_at: number;
  readonly metadata: Record<string, unknown>;

  constructor(params: {
    token: string;
    subject: string;
    scopes: string[];
    execution_id: string | null;
    jti: string;
    issued_at: number;
    expires_at: number;
    metadata?: Record<string, unknown>;
  }) {
    this.token = params.token;
    this.subject = params.subject;
    this.scopes = [...params.scopes];
    this.execution_id = params.execution_id;
    this.jti = params.jti;
    this.issued_at = params.issued_at;
    this.expires_at = params.expires_at;
    this.metadata = { ...(params.metadata ?? {}) };
  }

  grants(requested: string): boolean {
    return scopeGranted(this.scopes, requested);
  }

  require(requested: string): void {
    if (!this.grants(requested)) {
      throw new InsufficientScope(this.scopes, requested);
    }
  }

  seconds_until_expiry(now?: number): number {
    return this.expires_at - (now ?? Date.now() / 1000);
  }
}

export interface ConsentIssuerOptions {
  signing_key: string | Buffer;
  algorithm?: Algorithm;
  issuer?: string;
  default_ttl_seconds?: number;
  /** Clock for `iat` / `exp` generation. Defaults to Date.now()/1000. */
  clock?: () => number;
}

export class ConsentIssuer {
  readonly signing_key: string | Buffer;
  readonly algorithm: Algorithm;
  readonly issuer: string;
  readonly default_ttl_seconds: number;
  private readonly _clock: () => number;

  constructor(opts: ConsentIssuerOptions) {
    this.signing_key = opts.signing_key;
    this.algorithm = opts.algorithm ?? "HS256";
    this.issuer = opts.issuer ?? "iaiso";
    this.default_ttl_seconds = opts.default_ttl_seconds ?? 3600.0;
    this._clock = opts.clock ?? (() => Date.now() / 1000);
  }

  issue(params: {
    subject: string;
    scopes: string[];
    execution_id?: string | null;
    ttl_seconds?: number | null;
    metadata?: Record<string, unknown> | null;
  }): ConsentScope {
    const now = this._clock();
    const ttl = params.ttl_seconds ?? this.default_ttl_seconds;
    const exp = now + ttl;
    const jti = randomUUID();

    const payload: Record<string, unknown> = {
      iss: this.issuer,
      sub: params.subject,
      iat: Math.floor(now),
      exp: Math.floor(exp),
      jti,
      scopes: params.scopes,
    };
    if (params.execution_id != null) {
      payload.execution_id = params.execution_id;
    }
    if (params.metadata && Object.keys(params.metadata).length > 0) {
      payload.metadata = params.metadata;
    }

    const token = jwt.sign(payload, this.signing_key, {
      algorithm: this.algorithm,
    });

    return new ConsentScope({
      token,
      subject: params.subject,
      scopes: [...params.scopes],
      execution_id: params.execution_id ?? null,
      jti,
      issued_at: now,
      expires_at: exp,
      metadata: params.metadata ?? {},
    });
  }
}

/** In-memory revocation list. For production, back with Redis or similar. */
export class RevocationList {
  private readonly _revoked = new Set<string>();

  revoke(jti: string): void {
    this._revoked.add(jti);
  }

  is_revoked(jti: string): boolean {
    return this._revoked.has(jti);
  }

  get size(): number {
    return this._revoked.size;
  }
}

export interface ConsentVerifierOptions {
  verification_key: string | Buffer;
  algorithm?: Algorithm;
  issuer?: string;
  revocation_list?: RevocationList | null;
  leeway_seconds?: number;
  /** Clock for `exp` checks. Defaults to Date.now()/1000. */
  clock?: () => number;
}

export class ConsentVerifier {
  readonly verification_key: string | Buffer;
  readonly algorithm: Algorithm;
  readonly issuer: string;
  readonly revocation_list: RevocationList | null;
  readonly leeway_seconds: number;
  private readonly _clock: () => number;

  constructor(opts: ConsentVerifierOptions) {
    this.verification_key = opts.verification_key;
    this.algorithm = opts.algorithm ?? "HS256";
    this.issuer = opts.issuer ?? "iaiso";
    this.revocation_list = opts.revocation_list ?? null;
    this.leeway_seconds = opts.leeway_seconds ?? 5.0;
    this._clock = opts.clock ?? (() => Date.now() / 1000);
  }

  verify(token: string, opts: { execution_id?: string | null } = {}): ConsentScope {
    let payload: jwt.JwtPayload;
    const now = this._clock();

    try {
      const decoded = jwt.verify(token, this.verification_key, {
        algorithms: [this.algorithm],
        issuer: this.issuer,
        clockTimestamp: Math.floor(now),
        clockTolerance: this.leeway_seconds,
      });
      if (typeof decoded === "string") {
        throw new InvalidToken("token payload must be an object");
      }
      payload = decoded;
    } catch (err) {
      // Preserve our error taxonomy on expiry
      if (err instanceof ConsentError) throw err;
      const e = err as { name?: string; message?: string };
      if (e.name === "TokenExpiredError") {
        throw new ExpiredToken(e.message ?? "token expired");
      }
      throw new InvalidToken(e.message ?? String(err));
    }

    // Required claims per spec §2
    for (const required of ["exp", "iat", "jti", "sub", "iss"] as const) {
      if (payload[required] === undefined) {
        throw new InvalidToken(`missing required claim: ${required}`);
      }
    }

    const jti = String(payload.jti);
    if (this.revocation_list?.is_revoked(jti)) {
      throw new RevokedToken(`token ${jti} has been revoked`);
    }

    const tokenExec =
      typeof payload.execution_id === "string" ? payload.execution_id : null;
    if (opts.execution_id != null && tokenExec != null) {
      if (tokenExec !== opts.execution_id) {
        throw new InvalidToken(
          `token bound to execution ${JSON.stringify(tokenExec)}, requested ${JSON.stringify(opts.execution_id)}`,
        );
      }
    }

    return new ConsentScope({
      token,
      subject: String(payload.sub),
      scopes: Array.isArray(payload.scopes) ? (payload.scopes as string[]) : [],
      execution_id: tokenExec,
      jti,
      issued_at: Number(payload.iat),
      expires_at: Number(payload.exp),
      metadata:
        typeof payload.metadata === "object" && payload.metadata !== null
          ? (payload.metadata as Record<string, unknown>)
          : {},
    });
  }
}

/** Generate a cryptographically strong HS256 secret. */
export function generateHs256Secret(): string {
  // 64 bytes → 86-char base64url, well above the 256-bit minimum.
  const { randomBytes } = require("node:crypto") as typeof import("node:crypto");
  return randomBytes(64).toString("base64url");
}

export {
  ConsentError,
  InvalidToken,
  ExpiredToken,
  RevokedToken,
  InsufficientScope,
} from "./errors.js";
