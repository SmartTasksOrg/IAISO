# frozen_string_literal: true

module IAIso
  module Conformance
    autoload :VectorResult,    "iaiso/conformance/result"
    autoload :SectionResults,  "iaiso/conformance/result"
    autoload :PressureRunner,  "iaiso/conformance/pressure_runner"
    autoload :ConsentRunner,   "iaiso/conformance/consent_runner"
    autoload :EventsRunner,    "iaiso/conformance/events_runner"
    autoload :PolicyRunner,    "iaiso/conformance/policy_runner"
    autoload :Runner,          "iaiso/conformance/runner"
  end
end
