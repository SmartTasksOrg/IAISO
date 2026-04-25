# frozen_string_literal: true

module IAIso
  # Scope-based consent token issuance and verification.
  module Consent
    autoload :Algorithm,                "iaiso/consent/algorithm"
    autoload :ConsentError,             "iaiso/consent/errors"
    autoload :InvalidTokenError,        "iaiso/consent/errors"
    autoload :ExpiredTokenError,        "iaiso/consent/errors"
    autoload :RevokedTokenError,        "iaiso/consent/errors"
    autoload :InsufficientScopeError,   "iaiso/consent/errors"
    autoload :Scopes,                   "iaiso/consent/scopes"
    autoload :RevocationList,           "iaiso/consent/revocation_list"
    autoload :Scope,                    "iaiso/consent/scope"
    autoload :JWT,                      "iaiso/consent/jwt"
    autoload :Issuer,                   "iaiso/consent/issuer"
    autoload :Verifier,                 "iaiso/consent/verifier"
  end
end
