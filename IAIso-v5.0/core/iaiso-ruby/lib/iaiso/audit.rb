# frozen_string_literal: true

module IAIso
  # Audit-event envelope and base sinks.
  module Audit
    autoload :Event,         "iaiso/audit/event"
    autoload :Sink,          "iaiso/audit/sink"
    autoload :MemorySink,    "iaiso/audit/memory_sink"
    autoload :NullSink,      "iaiso/audit/null_sink"
    autoload :StdoutSink,    "iaiso/audit/stdout_sink"
    autoload :FanoutSink,    "iaiso/audit/fanout_sink"
    autoload :JSONLFileSink, "iaiso/audit/jsonl_file_sink"
  end
end
