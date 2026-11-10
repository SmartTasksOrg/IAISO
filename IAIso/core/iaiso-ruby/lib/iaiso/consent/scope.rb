# frozen_string_literal: true

require_relative "scopes"
require_relative "errors"

module IAIso
  module Consent
    # A verified consent scope.
    class Scope
      attr_reader :token, :subject, :scopes, :execution_id, :jti,
                  :issued_at, :expires_at, :metadata

      def initialize(token:, subject:, scopes:, execution_id:, jti:,
                     issued_at:, expires_at:, metadata: {})
        @token = token
        @subject = subject
        @scopes = scopes.freeze
        @execution_id = execution_id
        @jti = jti
        @issued_at = issued_at.to_i
        @expires_at = expires_at.to_i
        @metadata = metadata || {}
        freeze
      end

      def grants?(requested)
        Scopes.granted(@scopes, requested)
      end

      # Raises InsufficientScopeError if any of `required` is not granted.
      def require_scopes!(*required)
        required.flatten.each do |r|
          unless grants?(r)
            raise InsufficientScopeError.new(r, @scopes)
          end
        end
      end
    end
  end
end
