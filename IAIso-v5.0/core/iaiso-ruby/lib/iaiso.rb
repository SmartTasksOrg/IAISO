# frozen_string_literal: true

# IAIso — bounded-agent-execution framework, Ruby reference SDK.
# Conformant to IAIso spec 1.0.

require_relative "iaiso/version"

module IAIso
  # Capability submodules use autoload so consumers pay only for what
  # they require. `require "iaiso"` brings nothing in implicitly.
  autoload :Audit,         "iaiso/audit"
  autoload :Core,          "iaiso/core"
  autoload :Consent,       "iaiso/consent"
  autoload :Policy,        "iaiso/policy"
  autoload :Coordination,  "iaiso/coordination"
  autoload :Middleware,    "iaiso/middleware"
  autoload :Identity,      "iaiso/identity"
  autoload :Metrics,       "iaiso/metrics"
  autoload :Observability, "iaiso/observability"
  autoload :Conformance,   "iaiso/conformance"
  autoload :CLI,           "iaiso/cli"
end
