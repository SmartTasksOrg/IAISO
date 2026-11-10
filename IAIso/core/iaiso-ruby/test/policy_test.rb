# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/policy"

class PolicyTest < Minitest::Test
  def test_build_minimal_policy
    p = IAIso::Policy::Loader.build({ "version" => "1" })
    assert_equal "1", p.version
    assert_equal "sum", p.aggregator.name
  end

  def test_build_overrides_defaults
    p = IAIso::Policy::Loader.build({
      "version" => "1",
      "pressure" => { "escalation_threshold" => 0.7, "release_threshold" => 0.85 },
      "coordinator" => { "aggregator" => "max" },
    })
    assert_in_delta 0.7, p.pressure.escalation_threshold, 1e-9
    assert_equal "max", p.aggregator.name
  end

  def test_rejects_missing_version
    err = assert_raises(IAIso::Policy::PolicyError) do
      IAIso::Policy::Loader.build({ "metadata" => { "note" => "no version" } })
    end
    assert_match(/version/, err.message)
  end

  def test_rejects_bad_version
    assert_raises(IAIso::Policy::PolicyError) do
      IAIso::Policy::Loader.build({ "version" => "2" })
    end
  end

  def test_rejects_release_below_escalation
    assert_raises(IAIso::Policy::PolicyError) do
      IAIso::Policy::Loader.build({
        "version" => "1",
        "pressure" => { "escalation_threshold" => 0.9, "release_threshold" => 0.5 },
      })
    end
  end

  def test_rejects_string_as_number
    # Strict typing: string "0.015" should NOT validate as a number.
    assert_raises(IAIso::Policy::PolicyError) do
      IAIso::Policy::Loader.build({
        "version" => "1",
        "pressure" => { "token_coefficient" => "0.015" },
      })
    end
  end

  def test_rejects_top_level_array
    assert_raises(IAIso::Policy::PolicyError) do
      IAIso::Policy::Loader.build([1, 2, 3])
    end
  end

  def test_sum_aggregator
    assert_in_delta 0.8, IAIso::Policy::SumAggregator.new.aggregate({ "a" => 0.3, "b" => 0.5 }), 1e-9
  end

  def test_max_aggregator
    assert_in_delta 0.5, IAIso::Policy::MaxAggregator.new.aggregate({ "a" => 0.3, "b" => 0.5 }), 1e-9
  end

  def test_weighted_sum_aggregator
    a = IAIso::Policy::WeightedSumAggregator.new(weights: { "important" => 2.0 }, default_weight: 1.0)
    assert_in_delta 1.3, a.aggregate({ "important" => 0.5, "normal" => 0.3 }), 1e-9
  end
end
