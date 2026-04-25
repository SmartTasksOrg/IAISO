# frozen_string_literal: true

module IAIso
  module Policy
    autoload :PolicyError,           "iaiso/policy/errors"
    autoload :Aggregator,            "iaiso/policy/aggregator"
    autoload :SumAggregator,         "iaiso/policy/aggregator"
    autoload :MeanAggregator,        "iaiso/policy/aggregator"
    autoload :MaxAggregator,         "iaiso/policy/aggregator"
    autoload :WeightedSumAggregator, "iaiso/policy/aggregator"
    autoload :CoordinatorConfig,     "iaiso/policy/policy"
    autoload :ConsentPolicy,         "iaiso/policy/policy"
    autoload :Policy,                "iaiso/policy/policy"
    autoload :Loader,                "iaiso/policy/loader"
  end
end
