# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/conformance"

class ConformanceTest < Minitest::Test
  def test_all_vectors_pass
    spec_root = File.expand_path("../spec", __dir__)
    r = IAIso::Conformance::Runner.run_all(spec_root)
    failures = []
    [r.pressure, r.consent, r.events, r.policy].each do |bucket|
      bucket.each do |v|
        failures << "  [#{v.section}] #{v.name}: #{v.message}" unless v.passed
      end
    end
    assert_equal 67, r.total, "expected 67 total vectors"
    assert_equal r.total, r.passed,
                 "conformance #{r.passed}/#{r.total} — failures:\n#{failures.join("\n")}"
  end
end
