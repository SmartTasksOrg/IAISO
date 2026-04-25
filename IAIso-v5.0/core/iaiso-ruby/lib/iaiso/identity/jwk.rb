# frozen_string_literal: true

module IAIso
  module Identity
    # A single JWK key entry.
    Jwk = Data.define(:kty, :kid, :alg, :use, :n, :e) do
      def self.from_hash(h)
        new(
          kty: h["kty"].to_s,
          kid: h["kid"],
          alg: h["alg"],
          use: h["use"],
          n: h["n"],
          e: h["e"],
        )
      end
    end

    # JWKS document.
    Jwks = Data.define(:keys)
  end
end
