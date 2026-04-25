# frozen_string_literal: true

module IAIso
  module Identity
    autoload :IdentityError,  "iaiso/identity/errors"
    autoload :ProviderConfig, "iaiso/identity/provider_config"
    autoload :ScopeMapping,   "iaiso/identity/scope_mapping"
    autoload :Jwk,            "iaiso/identity/jwk"
    autoload :Jwks,           "iaiso/identity/jwk"
    autoload :OidcVerifier,   "iaiso/identity/oidc_verifier"
  end
end
