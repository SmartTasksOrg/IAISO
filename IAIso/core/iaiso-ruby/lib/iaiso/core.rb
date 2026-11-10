# frozen_string_literal: true

module IAIso
  # Pressure engine and bounded-execution facade.
  module Core
    autoload :Lifecycle,        "iaiso/core/lifecycle"
    autoload :StepOutcome,      "iaiso/core/step_outcome"
    autoload :Clock,            "iaiso/core/clock"
    autoload :WallClock,        "iaiso/core/clock"
    autoload :ScriptedClock,    "iaiso/core/clock"
    autoload :ClosureClock,     "iaiso/core/clock"
    autoload :ConfigError,      "iaiso/core/pressure_config"
    autoload :PressureConfig,   "iaiso/core/pressure_config"
    autoload :StepInput,        "iaiso/core/pressure_engine"
    autoload :PressureSnapshot, "iaiso/core/pressure_engine"
    autoload :EngineOptions,    "iaiso/core/pressure_engine"
    autoload :PressureEngine,   "iaiso/core/pressure_engine"
    autoload :BoundedExecution, "iaiso/core/bounded_execution"
  end
end
