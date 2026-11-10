# frozen_string_literal: true

require "json"

module IAIso
  module Audit
    # IAIso audit event envelope.
    #
    # The JSON form of this struct MUST emit fields in spec order:
    #   schema_version, execution_id, kind, timestamp, data
    # with `data` keys sorted alphabetically. Integer-valued floats
    # serialize as `0` not `0.0` to match the wire format of every
    # other reference SDK.
    class Event
      CURRENT_SCHEMA_VERSION = "1.0"

      attr_reader :schema_version, :execution_id, :kind, :timestamp, :data

      def initialize(execution_id:, kind:, timestamp:, data: {}, schema_version: CURRENT_SCHEMA_VERSION)
        @schema_version = schema_version.to_s
        @execution_id   = execution_id.to_s
        @kind           = kind.to_s
        @timestamp      = timestamp.to_f
        @data           = data || {}
      end

      # Serialize to canonical JSON. Field order is the spec order;
      # `data` keys are sorted alphabetically; integer-valued floats
      # emit as integers.
      def to_json(*_args)
        +"{" \
          "\"schema_version\":#{encode_string(@schema_version)}," \
          "\"execution_id\":#{encode_string(@execution_id)}," \
          "\"kind\":#{encode_string(@kind)}," \
          "\"timestamp\":#{encode_number(@timestamp)}," \
          "\"data\":#{encode_map(@data)}" \
          "}"
      end

      def ==(other)
        other.is_a?(Event) &&
          schema_version == other.schema_version &&
          execution_id == other.execution_id &&
          kind == other.kind &&
          timestamp == other.timestamp &&
          data == other.data
      end

      private

      def encode_map(m)
        return "{}" if m.empty?
        keys = m.keys.map(&:to_s).sort
        parts = keys.map do |k|
          v = m[k] || m[k.to_sym]
          "#{encode_string(k)}:#{encode_value(v)}"
        end
        "{#{parts.join(",")}}"
      end

      def encode_value(v)
        case v
        when nil          then "null"
        when true, false  then v.to_s
        when Integer      then v.to_s
        when Float        then encode_number(v)
        when String       then encode_string(v)
        when Symbol       then encode_string(v.to_s)
        when Array        then "[#{v.map { |x| encode_value(x) }.join(",")}]"
        when Hash         then encode_map(v)
        else encode_string(v.to_s)
        end
      end

      def encode_string(s)
        # Build a JSON-escaped string. We don't escape forward slashes
        # (matches the other reference SDKs).
        out = +'"'
        s.to_s.each_char do |ch|
          case ch
          when "\""       then out << '\\"'
          when "\\"       then out << "\\\\"
          when "\b"       then out << "\\b"
          when "\t"       then out << "\\t"
          when "\n"       then out << "\\n"
          when "\f"       then out << "\\f"
          when "\r"       then out << "\\r"
          else
            cp = ch.ord
            if cp < 0x20
              out << format("\\u%04x", cp)
            else
              out << ch
            end
          end
        end
        out << '"'
        out
      end

      def encode_number(n)
        return "null" if n.is_a?(Float) && (n.nan? || n.infinite?)
        if n.is_a?(Float) && n.finite? && (n % 1).zero? && n.abs < 1e16
          n.to_i.to_s
        else
          n.to_s
        end
      end
    end
  end
end
