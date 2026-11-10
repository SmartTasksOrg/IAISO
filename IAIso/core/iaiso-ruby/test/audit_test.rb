# frozen_string_literal: true

require_relative "test_helper"
require "iaiso/audit"
require "json"
require "tempfile"

class AuditTest < Minitest::Test
  def test_event_emits_fields_in_spec_order
    e = IAIso::Audit::Event.new(execution_id: "exec-1", kind: "engine.init", timestamp: 0.0, data: { "pressure" => 0.0 })
    json = e.to_json
    assert json.start_with?('{"schema_version":')
    assert_includes json, '"execution_id":"exec-1"'
    sv = json.index('"schema_version"')
    ei = json.index('"execution_id"')
    kn = json.index('"kind"')
    ts = json.index('"timestamp"')
    dt = json.index('"data"')
    assert sv < ei && ei < kn && kn < ts && ts < dt, "spec field order broken"
  end

  def test_integer_floats_serialize_as_integers
    e = IAIso::Audit::Event.new(execution_id: "e", kind: "k", timestamp: 0.0, data: { "n" => 0.0 })
    json = e.to_json
    assert_includes json, '"timestamp":0'
    refute_includes json, '"timestamp":0.0'
    assert_includes json, '"n":0'
    refute_includes json, '"n":0.0'
  end

  def test_data_keys_sorted_alphabetically
    e = IAIso::Audit::Event.new(execution_id: "e", kind: "k", timestamp: 0.0, data: { "z" => 1, "a" => 2, "m" => 3 })
    json = e.to_json
    a = json.index('"a"')
    m = json.index('"m"')
    z = json.index('"z"')
    assert a < m && m < z
  end

  def test_null_data_values_emit
    e = IAIso::Audit::Event.new(execution_id: "e", kind: "k", timestamp: 0.0, data: { "tag" => nil })
    assert_includes e.to_json, '"tag":null'
  end

  def test_memory_sink_stores_events
    s = IAIso::Audit::MemorySink.new
    s.emit(IAIso::Audit::Event.new(execution_id: "e", kind: "a", timestamp: 0.0))
    s.emit(IAIso::Audit::Event.new(execution_id: "e", kind: "b", timestamp: 0.0))
    assert_equal 2, s.events.size
    assert_equal "a", s.events[0].kind
  end

  def test_fanout_broadcasts
    a = IAIso::Audit::MemorySink.new
    b = IAIso::Audit::MemorySink.new
    f = IAIso::Audit::FanoutSink.new(a, b)
    f.emit(IAIso::Audit::Event.new(execution_id: "e", kind: "k", timestamp: 0.0))
    assert_equal 1, a.events.size
    assert_equal 1, b.events.size
  end

  def test_jsonl_file_sink_appends
    Tempfile.create("iaiso-audit-") do |tmp|
      sink = IAIso::Audit::JSONLFileSink.new(tmp.path)
      sink.emit(IAIso::Audit::Event.new(execution_id: "e", kind: "a", timestamp: 0.0))
      sink.emit(IAIso::Audit::Event.new(execution_id: "e", kind: "b", timestamp: 0.0))
      lines = File.readlines(tmp.path).map(&:strip).reject(&:empty?)
      assert_equal 2, lines.size
      lines.each do |l|
        obj = JSON.parse(l)
        assert obj.key?("schema_version")
      end
    end
  end

  def test_null_sink_swallows
    IAIso::Audit::NullSink.instance.emit(IAIso::Audit::Event.new(execution_id: "e", kind: "k", timestamp: 0.0))
    pass
  end
end
