# frozen_string_literal: true

require_relative "result"
require_relative "pressure_runner"
require_relative "consent_runner"
require_relative "events_runner"
require_relative "policy_runner"

module IAIso
  module Conformance
    module Runner
      module_function

      def run_all(spec_root)
        r = SectionResults.new
        r.pressure = PressureRunner.run(spec_root)
        r.consent  = ConsentRunner.run(spec_root)
        r.events   = EventsRunner.run(spec_root)
        r.policy   = PolicyRunner.run(spec_root)
        r
      end
    end
  end
end
