# frozen_string_literal: true

require "json"
require_relative "errors"
require_relative "aggregator"
require_relative "policy"

module IAIso
  module Policy
    # IAIso policy loader. JSON-only — the Ruby SDK doesn't depend on
    # a YAML parser to keep the dependency surface clean. Convert YAML
    # to JSON externally if needed.
    module Loader
      SCOPE_PATTERN = /\A[a-z0-9_-]+(\.[a-z0-9_-]+)*\z/.freeze

      module_function

      # Validate a parsed JSON document against spec/policy/README.md.
      def validate!(doc)
        unless doc.is_a?(Hash)
          raise PolicyError, "$: policy document must be a mapping"
        end
        unless doc.key?("version")
          raise PolicyError, "$: required property 'version' missing"
        end
        v = doc["version"]
        unless v.is_a?(String) && v == "1"
          raise PolicyError, "$.version: must be exactly \"1\", got #{repr(v)}"
        end

        if doc.key?("pressure")
          p = doc["pressure"]
          unless p.is_a?(Hash)
            raise PolicyError, "$.pressure: must be a mapping"
          end
          %w[token_coefficient tool_coefficient depth_coefficient
             dissipation_per_step dissipation_per_second].each do |f|
            next unless p.key?(f)
            n = numeric_value(p[f])
            raise PolicyError, "$.pressure.#{f}: expected number" if n.nil?
            raise PolicyError, "$.pressure.#{f}: must be non-negative (got #{n})" if n < 0
          end
          %w[escalation_threshold release_threshold].each do |f|
            next unless p.key?(f)
            n = numeric_value(p[f])
            raise PolicyError, "$.pressure.#{f}: expected number" if n.nil?
            unless (0..1).cover?(n)
              raise PolicyError, "$.pressure.#{f}: must be in [0, 1] (got #{n})"
            end
          end
          if p.key?("post_release_lock")
            unless [true, false].include?(p["post_release_lock"])
              raise PolicyError, "$.pressure.post_release_lock: expected boolean"
            end
          end
          esc = numeric_value(p["escalation_threshold"])
          rel = numeric_value(p["release_threshold"])
          if esc && rel && rel <= esc
            raise PolicyError,
                  "$.pressure.release_threshold: must exceed escalation_threshold (#{rel} <= #{esc})"
          end
        end

        if doc.key?("coordinator")
          c = doc["coordinator"]
          unless c.is_a?(Hash)
            raise PolicyError, "$.coordinator: must be a mapping"
          end
          if c.key?("aggregator")
            name = c["aggregator"]
            unless name.is_a?(String) && %w[sum mean max weighted_sum].include?(name)
              raise PolicyError,
                    "$.coordinator.aggregator: must be one of sum|mean|max|weighted_sum (got #{repr(name)})"
            end
          end
          esc = numeric_value(c["escalation_threshold"])
          rel = numeric_value(c["release_threshold"])
          if esc && rel && rel <= esc
            raise PolicyError,
                  "$.coordinator.release_threshold: must exceed escalation_threshold (#{rel} <= #{esc})"
          end
        end

        if doc.key?("consent")
          c = doc["consent"]
          unless c.is_a?(Hash)
            raise PolicyError, "$.consent: must be a mapping"
          end
          if c.key?("required_scopes")
            scopes = c["required_scopes"]
            unless scopes.is_a?(Array)
              raise PolicyError, "$.consent.required_scopes: expected list"
            end
            scopes.each_with_index do |s, i|
              unless s.is_a?(String) && SCOPE_PATTERN.match?(s)
                raise PolicyError,
                      "$.consent.required_scopes[#{i}]: #{repr(s)} is not a valid scope"
              end
            end
          end
        end
      end

      # Build a Policy from a parsed JSON document.
      def build(doc)
        validate!(doc)

        # Build PressureConfig with overrides.
        pkw = {}
        if doc["pressure"].is_a?(Hash)
          p = doc["pressure"]
          %w[escalation_threshold release_threshold dissipation_per_step
             dissipation_per_second token_coefficient tool_coefficient
             depth_coefficient].each do |f|
            n = numeric_value(p[f])
            pkw[f.to_sym] = n unless n.nil?
          end
          if [true, false].include?(p["post_release_lock"])
            pkw[:post_release_lock] = p["post_release_lock"]
          end
        end
        require "iaiso/core"
        pressure = IAIso::Core::PressureConfig.new(**pkw)
        begin
          pressure.validate!
        rescue IAIso::Core::ConfigError => e
          raise PolicyError, "$.pressure: #{e.message}"
        end

        coord = CoordinatorConfig.defaults
        aggregator = SumAggregator.new
        if doc["coordinator"].is_a?(Hash)
          c = doc["coordinator"]
          coord = CoordinatorConfig.new(
            escalation_threshold: numeric_value(c["escalation_threshold"]) || coord.escalation_threshold,
            release_threshold:    numeric_value(c["release_threshold"]) || coord.release_threshold,
            notify_cooldown_seconds: numeric_value(c["notify_cooldown_seconds"]) || coord.notify_cooldown_seconds,
          )
          aggregator = build_aggregator(c)
        end

        consent = ConsentPolicy.defaults
        if doc["consent"].is_a?(Hash)
          c = doc["consent"]
          consent = ConsentPolicy.new(
            issuer: c["issuer"].is_a?(String) ? c["issuer"] : nil,
            default_ttl_seconds: numeric_value(c["default_ttl_seconds"]) || consent.default_ttl_seconds,
            required_scopes: c["required_scopes"].is_a?(Array) ? c["required_scopes"].map(&:to_s) : consent.required_scopes,
            allowed_algorithms: c["allowed_algorithms"].is_a?(Array) ? c["allowed_algorithms"].map(&:to_s) : consent.allowed_algorithms,
          )
        end

        metadata = doc["metadata"].is_a?(Hash) ? doc["metadata"] : {}

        Policy.new(
          version: "1",
          pressure: pressure,
          coordinator: coord,
          consent: consent,
          aggregator: aggregator,
          metadata: metadata,
        )
      end

      def parse_json(data)
        doc = ::JSON.parse(data)
        build(doc)
      rescue ::JSON::ParserError => e
        raise PolicyError, "policy JSON parse failed: #{e.message}"
      end

      def load(path)
        unless path.to_s.downcase.end_with?(".json")
          raise PolicyError,
                "unsupported policy file extension: #{path} (only .json is supported in the Ruby SDK)"
        end
        parse_json(File.read(path))
      end

      def build_aggregator(coord)
        case coord["aggregator"]
        when "mean" then MeanAggregator.new
        when "max"  then MaxAggregator.new
        when "weighted_sum"
          weights = coord["weights"].is_a?(Hash) ? coord["weights"].transform_values(&:to_f) : {}
          dw = numeric_value(coord["default_weight"]) || 1.0
          WeightedSumAggregator.new(weights: weights, default_weight: dw)
        else
          SumAggregator.new
        end
      end

      # Strict numeric extractor. Returns nil for strings (the gotcha
      # we caught in Java) and for true/false (Ruby distinguishes Bool
      # from Numeric cleanly, no NSNumber-style ambiguity).
      def numeric_value(v)
        return nil if v.nil?
        return nil if v.is_a?(String)
        return nil if v == true || v == false
        return v.to_f if v.is_a?(Numeric)
        nil
      end

      def repr(v)
        ::JSON.generate(v)
      rescue StandardError
        v.inspect
      end
    end
  end
end
