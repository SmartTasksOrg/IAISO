# frozen_string_literal: true

module IAIso
  module Consent
    # Scope-matching logic.
    module Scopes
      module_function

      # Returns true iff the requested scope is granted by any in `granted`.
      # Match rules per spec/consent/README.md:
      #   - Exact match: granted "tools.search" satisfies requested "tools.search".
      #   - Prefix-at-segment-boundary: granted "tools" satisfies "tools.search".
      #   - Substring without boundary does NOT match: "tools" vs "toolsbar".
      #   - More-specific does NOT satisfy less-specific: "tools.search.bulk"
      #     does not satisfy "tools.search".
      #
      # Raises ArgumentError if requested is empty.
      def granted(granted, requested)
        raise ArgumentError, "requested scope must be non-empty" if requested.nil? || requested.empty?
        Array(granted).any? do |g|
          g == requested || requested.start_with?("#{g}.")
        end
      end
    end
  end
end
