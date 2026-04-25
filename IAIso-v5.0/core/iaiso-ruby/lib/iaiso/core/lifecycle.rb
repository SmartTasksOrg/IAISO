# frozen_string_literal: true

module IAIso
  module Core
    # Lifecycle states for a PressureEngine. The string value is the wire form.
    module Lifecycle
      INIT      = "init"
      RUNNING   = "running"
      ESCALATED = "escalated"
      RELEASED  = "released"
      LOCKED    = "locked"

      ALL = [INIT, RUNNING, ESCALATED, RELEASED, LOCKED].freeze
    end
  end
end
