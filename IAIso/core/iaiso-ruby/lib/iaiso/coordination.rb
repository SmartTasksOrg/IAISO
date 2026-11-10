# frozen_string_literal: true

module IAIso
  module Coordination
    autoload :Lifecycle,                  "iaiso/coordination/lifecycle"
    autoload :CoordinatorError,           "iaiso/coordination/errors"
    autoload :Snapshot,                   "iaiso/coordination/snapshot"
    autoload :SharedPressureCoordinator,  "iaiso/coordination/shared_pressure_coordinator"
    autoload :RedisClient,                "iaiso/coordination/redis_coordinator"
    autoload :RedisCoordinator,           "iaiso/coordination/redis_coordinator"
  end
end
