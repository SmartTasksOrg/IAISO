/**
 * Consent error hierarchy. Mirrors iaiso.consent exceptions in the Python
 * reference. See spec/consent/README.md §7 for the normative semantics.
 */

export class ConsentError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConsentError";
  }
}

export class InvalidToken extends ConsentError {
  constructor(message: string) {
    super(message);
    this.name = "InvalidToken";
  }
}

export class ExpiredToken extends ConsentError {
  constructor(message: string) {
    super(message);
    this.name = "ExpiredToken";
  }
}

export class RevokedToken extends ConsentError {
  constructor(message: string) {
    super(message);
    this.name = "RevokedToken";
  }
}

export class InsufficientScope extends ConsentError {
  readonly granted: string[];
  readonly requested: string;

  constructor(granted: string[], requested: string) {
    super(
      `scope '${requested}' not granted by token (granted: [${granted.join(", ")}])`,
    );
    this.name = "InsufficientScope";
    this.granted = granted;
    this.requested = requested;
  }
}
