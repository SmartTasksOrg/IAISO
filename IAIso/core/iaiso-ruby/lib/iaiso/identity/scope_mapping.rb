# frozen_string_literal: true

module IAIso
  module Identity
    # Configures how OIDC claims become IAIso scopes.
    class ScopeMapping
      attr_reader :direct_claims, :group_to_scopes, :always_grant

      def initialize(direct_claims: [], group_to_scopes: {}, always_grant: [])
        @direct_claims = direct_claims.map(&:to_s).freeze
        @group_to_scopes = group_to_scopes.transform_values { |v| Array(v).map(&:to_s) }.freeze
        @always_grant = always_grant.map(&:to_s).freeze
        freeze
      end

      def self.defaults = new
    end
  end
end
