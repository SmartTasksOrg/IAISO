# frozen_string_literal: true

module IAIso
  module Coordination
    Snapshot = Data.define(
      :coordinator_id,
      :aggregate_pressure,
      :lifecycle,
      :active_executions,
      :per_execution,
    )
  end
end
