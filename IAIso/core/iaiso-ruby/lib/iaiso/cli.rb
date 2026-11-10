# frozen_string_literal: true

require "json"

module IAIso
  module CLI
    module_function

    HELP = <<~HELP
      IAIso admin CLI

      Subcommands:
        policy validate <file>                 check a policy JSON file for errors
        policy template <file>                 write a blank policy template
        consent issue <sub> <scope,...> [ttl]  issue a token (needs IAISO_HS256_SECRET)
        consent verify <token>                 verify a token
        audit tail <jsonl-file>                pretty-print JSONL audit events
        audit stats <jsonl-file>               summarize events by kind
        coordinator demo                       in-memory coordinator smoke test
        conformance <spec-dir>                 run the conformance suite
    HELP

    POLICY_TEMPLATE = <<~JSON
      {
        "version": "1",
        "pressure": {
          "escalation_threshold": 0.85,
          "release_threshold": 0.95,
          "token_coefficient": 0.015,
          "tool_coefficient": 0.08,
          "depth_coefficient": 0.05,
          "dissipation_per_step": 0.02,
          "dissipation_per_second": 0.0,
          "post_release_lock": true
        },
        "coordinator": {
          "aggregator": "sum",
          "escalation_threshold": 5.0,
          "release_threshold": 8.0,
          "notify_cooldown_seconds": 1.0
        },
        "consent": {
          "issuer": "iaiso",
          "default_ttl_seconds": 3600,
          "required_scopes": [],
          "allowed_algorithms": ["HS256", "RS256"]
        },
        "metadata": {}
      }
    JSON

    def run(argv)
      argv = argv.dup
      if argv.empty? || argv.first == "--help" || argv.first == "-h"
        puts HELP
        return 0
      end
      cmd = argv.shift
      case cmd
      when "policy"      then cmd_policy(argv)
      when "consent"     then cmd_consent(argv)
      when "audit"       then cmd_audit(argv)
      when "coordinator" then cmd_coordinator(argv)
      when "conformance" then cmd_conformance(argv)
      else
        warn "unknown command: #{cmd}"
        puts HELP
        2
      end
    end

    def cmd_policy(args)
      require "iaiso/policy"
      sub = args.shift
      case sub
      when "validate"
        path = args.shift or (warn("usage: iaiso policy validate <file>"); return 2)
        begin
          p = IAIso::Policy::Loader.load(path)
          puts "OK: policy v#{p.version}"
          puts "  pressure.escalation_threshold = #{p.pressure.escalation_threshold}"
          puts "  coordinator.aggregator        = #{p.aggregator.name}"
          puts "  consent.issuer                = #{p.consent.issuer || "(none)"}"
          0
        rescue StandardError => e
          warn "INVALID: #{e.message}"
          1
        end
      when "template"
        path = args.shift or (warn("usage: iaiso policy template <file>"); return 2)
        File.write(path, POLICY_TEMPLATE)
        puts "Wrote template to #{path}"
        0
      else
        warn "unknown policy subcommand: #{sub}"
        2
      end
    end

    def cmd_consent(args)
      require "iaiso/consent"
      sub = args.shift
      secret = ENV["IAISO_HS256_SECRET"]
      if secret.nil? || secret.empty?
        warn "error: IAISO_HS256_SECRET must be set in the environment"
        return 2
      end
      case sub
      when "issue"
        if args.size < 2
          warn "usage: iaiso consent issue <subject> <scope1,scope2,...> [ttl_seconds]"
          return 2
        end
        subject = args.shift
        scopes_csv = args.shift
        ttl = (args.shift || "3600").to_i
        scopes = scopes_csv.split(",").map(&:strip).reject(&:empty?)
        issuer = IAIso::Consent::Issuer.new(
          algorithm: IAIso::Consent::Algorithm::HS256,
          issuer: "iaiso",
          hs_key: secret,
          default_ttl_seconds: ttl,
        )
        scope = issuer.issue(subject: subject, scopes: scopes, ttl_seconds: ttl)
        puts JSON.pretty_generate({
          token: scope.token,
          subject: scope.subject,
          scopes: scope.scopes,
          jti: scope.jti,
          expires_at: scope.expires_at,
        })
        0
      when "verify"
        token = args.shift or (warn("usage: iaiso consent verify <token>"); return 2)
        verifier = IAIso::Consent::Verifier.new(
          algorithm: IAIso::Consent::Algorithm::HS256,
          issuer: "iaiso",
          hs_key: secret,
        )
        begin
          s = verifier.verify(token)
          out = {
            status: "valid",
            subject: s.subject,
            scopes: s.scopes,
            jti: s.jti,
            expires_at: s.expires_at,
          }
          out[:execution_id] = s.execution_id if s.execution_id
          puts JSON.pretty_generate(out)
          0
        rescue IAIso::Consent::ExpiredTokenError => e
          warn "expired: #{e.message}"; 1
        rescue IAIso::Consent::RevokedTokenError => e
          warn "revoked: #{e.message}"; 1
        rescue StandardError => e
          warn "invalid: #{e.message}"; 1
        end
      else
        warn "unknown consent subcommand: #{sub}"
        2
      end
    end

    def cmd_audit(args)
      sub = args.shift
      path = args.shift
      if path.nil?
        warn "usage: iaiso audit [tail|stats] <jsonl-file>"
        return 2
      end
      data =
        begin
          File.read(path)
        rescue StandardError
          warn "open #{path} failed"
          return 1
        end
      case sub
      when "tail"
        data.each_line do |line|
          line = line.strip
          next if line.empty?
          begin
            ev = JSON.parse(line)
            ts = ev["timestamp"].is_a?(Numeric) ? format("%.3f", ev["timestamp"]) : "?"
            kind = ev["kind"] || "?"
            exec = ev["execution_id"] || "?"
            puts format("%-15s  %-28s  %s", ts, kind, exec)
          rescue StandardError
            puts "  [unparseable] #{line[0, 80]}"
          end
        end
        0
      when "stats"
        counts = Hash.new(0)
        executions = {}
        total = 0
        data.each_line do |line|
          line = line.strip
          next if line.empty?
          begin
            ev = JSON.parse(line)
            total += 1
            counts[ev["kind"]] += 1 if ev["kind"]
            executions[ev["execution_id"]] = true if ev["execution_id"]
          rescue StandardError
            # skip
          end
        end
        puts "total events: #{total}"
        puts "distinct executions: #{executions.size}"
        counts.sort_by { |_, n| -n }.each do |k, n|
          puts format("  %6d  %s", n, k)
        end
        0
      else
        warn "unknown audit subcommand: #{sub}"
        2
      end
    end

    def cmd_coordinator(args)
      sub = args.shift
      unless sub == "demo"
        warn "usage: iaiso coordinator demo"
        return 2
      end
      require "iaiso/audit"
      require "iaiso/coordination"
      require "iaiso/policy"
      c = IAIso::Coordination::SharedPressureCoordinator.new(
        coordinator_id: "cli-demo",
        escalation_threshold: 1.5,
        release_threshold: 2.5,
        notify_cooldown_seconds: 0.0,
        aggregator: IAIso::Policy::SumAggregator.new,
        audit_sink: IAIso::Audit::MemorySink.new,
        on_escalation: ->(s) { puts format("  [callback] ESCALATION at aggregate=%.3f", s.aggregate_pressure) },
        on_release:    ->(s) { puts format("  [callback] RELEASE at aggregate=%.3f", s.aggregate_pressure) },
      )
      workers = ["worker-a", "worker-b", "worker-c"]
      workers.each { |w| c.register(w) }
      puts "Demo: 3 workers registered. Stepping pressures..."
      [0.3, 0.6, 0.9, 0.6].each_with_index do |p, i|
        workers.each { |w| c.update(w, p) }
        snap = c.snapshot
        puts format("  step %d: per-worker=%.2f  aggregate=%.3f  lifecycle=%s",
                    i + 1, p, snap.aggregate_pressure, snap.lifecycle)
      end
      0
    end

    def cmd_conformance(args)
      require "iaiso/conformance"
      spec_root = args.shift || "./spec"
      r = IAIso::Conformance::Runner.run_all(spec_root)
      sections = { "pressure" => r.pressure, "consent" => r.consent,
                   "events" => r.events, "policy" => r.policy }
      fail = 0
      sections.each do |name, bucket|
        pass = bucket.count(&:passed)
        total = bucket.size
        tag = pass == total ? "PASS" : "FAIL"
        if pass != total
          fail += total - pass
          bucket.reject(&:passed).each do |v|
            puts "  [#{name}] #{v.name}: #{v.message}"
          end
        end
        puts "[#{tag}] #{name}: #{pass}/#{total}"
      end
      puts ""
      puts "conformance: #{r.passed}/#{r.total} vectors passed"
      fail.positive? ? 1 : 0
    rescue StandardError => e
      warn "error: #{e.message}"
      1
    end
  end
end
