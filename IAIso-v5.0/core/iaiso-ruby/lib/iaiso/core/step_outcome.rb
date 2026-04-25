# frozen_string_literal: true

module IAIso
  module Core
    # Outcome of a single PressureEngine#step call. Wire form = string value.
    module StepOutcome
      OK         = "ok"
      ESCALATED  = "escalated"
      RELEASED   = "released"
      LOCKED     = "locked"

      ALL = [OK, ESCALATED, RELEASED, LOCKED].freeze
    end
  end
end
