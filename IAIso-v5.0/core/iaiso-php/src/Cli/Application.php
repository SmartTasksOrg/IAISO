<?php

declare(strict_types=1);

namespace IAIso\Cli;

use IAIso\Audit\MemorySink;
use IAIso\Conformance\ConformanceRunner;
use IAIso\Conformance\VectorResult;
use IAIso\Consent\Algorithm;
use IAIso\Consent\ExpiredTokenException;
use IAIso\Consent\InvalidTokenException;
use IAIso\Consent\Issuer;
use IAIso\Consent\RevokedTokenException;
use IAIso\Consent\Verifier;
use IAIso\Coordination\SharedPressureCoordinator;
use IAIso\Policy\PolicyLoader;
use IAIso\Policy\SumAggregator;

/** IAIso admin CLI. */
final class Application
{
    /** @param string[] $argv */
    public static function run(array $argv): int
    {
        $argv = array_slice($argv, 1);
        if (count($argv) === 0 || $argv[0] === '--help' || $argv[0] === '-h') {
            self::printHelp();
            return 0;
        }
        $cmd = $argv[0];
        $rest = array_slice($argv, 1);
        return match ($cmd) {
            'policy'      => self::cmdPolicy($rest),
            'consent'     => self::cmdConsent($rest),
            'audit'       => self::cmdAudit($rest),
            'coordinator' => self::cmdCoordinator($rest),
            'conformance' => self::cmdConformance($rest),
            default       => (function () use ($cmd) {
                fwrite(STDERR, "unknown command: $cmd\n");
                self::printHelp();
                return 2;
            })(),
        };
    }

    private static function printHelp(): void
    {
        echo <<<EOT
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

EOT;
    }

    /** @param string[] $args */
    private static function cmdPolicy(array $args): int
    {
        if (count($args) === 0) {
            fwrite(STDERR, "usage: iaiso policy [validate|template] <file>\n");
            return 2;
        }
        if ($args[0] === 'validate') {
            if (count($args) !== 2) {
                fwrite(STDERR, "usage: iaiso policy validate <file>\n");
                return 2;
            }
            try {
                $p = PolicyLoader::load($args[1]);
                echo "OK: policy v{$p->version}\n";
                echo "  pressure.escalation_threshold = {$p->pressure->escalationThreshold}\n";
                echo "  coordinator.aggregator        = " . $p->aggregator->name() . "\n";
                $iss = $p->consent->issuer ?? '(none)';
                echo "  consent.issuer                = $iss\n";
                return 0;
            } catch (\Throwable $e) {
                fwrite(STDERR, 'INVALID: ' . $e->getMessage() . "\n");
                return 1;
            }
        }
        if ($args[0] === 'template') {
            if (count($args) !== 2) {
                fwrite(STDERR, "usage: iaiso policy template <file>\n");
                return 2;
            }
            $body = <<<JSON
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

JSON;
            $r = @file_put_contents($args[1], $body);
            if ($r === false) {
                fwrite(STDERR, "write {$args[1]} failed\n");
                return 1;
            }
            echo "Wrote template to {$args[1]}\n";
            return 0;
        }
        fwrite(STDERR, "unknown policy subcommand: {$args[0]}\n");
        return 2;
    }

    /** @param string[] $args */
    private static function cmdConsent(array $args): int
    {
        if (count($args) === 0) {
            fwrite(STDERR, "usage: iaiso consent [issue|verify] ...\n");
            return 2;
        }
        $secret = getenv('IAISO_HS256_SECRET');
        if ($secret === false || $secret === '') {
            fwrite(STDERR, "error: IAISO_HS256_SECRET must be set in the environment\n");
            return 2;
        }
        if ($args[0] === 'issue') {
            if (count($args) < 3) {
                fwrite(STDERR, "usage: iaiso consent issue <subject> <scope1,scope2,...> [ttl_seconds]\n");
                return 2;
            }
            $ttl = isset($args[3]) ? (int) $args[3] : 3600;
            $scopes = array_values(array_filter(
                array_map('trim', explode(',', $args[2])),
                fn($s) => $s !== '',
            ));
            $issuer = Issuer::builder()
                ->hsKey($secret)->algorithm(Algorithm::HS256)
                ->issuer('iaiso')->defaultTtlSeconds($ttl)->build();
            try {
                $scope = $issuer->issue($args[1], $scopes, null, $ttl, null);
                echo json_encode([
                    'token' => $scope->token,
                    'subject' => $scope->subject,
                    'scopes' => $scope->scopes,
                    'jti' => $scope->jti,
                    'expires_at' => $scope->expiresAt,
                ], JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
                return 0;
            } catch (\Throwable $e) {
                fwrite(STDERR, 'issue failed: ' . $e->getMessage() . "\n");
                return 1;
            }
        }
        if ($args[0] === 'verify') {
            if (count($args) !== 2) {
                fwrite(STDERR, "usage: iaiso consent verify <token>\n");
                return 2;
            }
            $verifier = Verifier::builder()
                ->hsKey($secret)->algorithm(Algorithm::HS256)
                ->issuer('iaiso')->build();
            try {
                $s = $verifier->verify($args[1]);
                $out = [
                    'status' => 'valid',
                    'subject' => $s->subject,
                    'scopes' => $s->scopes,
                    'jti' => $s->jti,
                    'expires_at' => $s->expiresAt,
                ];
                if ($s->executionId !== null) $out['execution_id'] = $s->executionId;
                echo json_encode($out, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n";
                return 0;
            } catch (ExpiredTokenException $e) {
                fwrite(STDERR, 'expired: ' . $e->getMessage() . "\n");
                return 1;
            } catch (RevokedTokenException $e) {
                fwrite(STDERR, 'revoked: ' . $e->getMessage() . "\n");
                return 1;
            } catch (\Throwable $e) {
                fwrite(STDERR, 'invalid: ' . $e->getMessage() . "\n");
                return 1;
            }
        }
        fwrite(STDERR, "unknown consent subcommand: {$args[0]}\n");
        return 2;
    }

    /** @param string[] $args */
    private static function cmdAudit(array $args): int
    {
        if (count($args) === 0) {
            fwrite(STDERR, "usage: iaiso audit [tail|stats] <jsonl-file>\n");
            return 2;
        }
        if ($args[0] === 'tail') {
            if (count($args) !== 2) {
                fwrite(STDERR, "usage: iaiso audit tail <jsonl-file>\n");
                return 2;
            }
            return self::tailJsonl($args[1]);
        }
        if ($args[0] === 'stats') {
            if (count($args) !== 2) {
                fwrite(STDERR, "usage: iaiso audit stats <jsonl-file>\n");
                return 2;
            }
            return self::statsJsonl($args[1]);
        }
        fwrite(STDERR, "unknown audit subcommand: {$args[0]}\n");
        return 2;
    }

    private static function tailJsonl(string $path): int
    {
        $data = @file_get_contents($path);
        if ($data === false) {
            fwrite(STDERR, "open $path failed\n");
            return 1;
        }
        foreach (explode("\n", $data) as $line) {
            $line = trim($line);
            if ($line === '') continue;
            try {
                $ev = json_decode($line, true, 512, JSON_THROW_ON_ERROR);
                $ts = isset($ev['timestamp']) ? sprintf('%.3f', (float) $ev['timestamp']) : '?';
                $kind = $ev['kind'] ?? '?';
                $exec = $ev['execution_id'] ?? '?';
                printf("%-15s  %-28s  %s\n", $ts, $kind, $exec);
            } catch (\Throwable) {
                $trunc = strlen($line) > 80 ? substr($line, 0, 80) : $line;
                echo "  [unparseable] $trunc\n";
            }
        }
        return 0;
    }

    private static function statsJsonl(string $path): int
    {
        $data = @file_get_contents($path);
        if ($data === false) {
            fwrite(STDERR, "open $path failed\n");
            return 1;
        }
        $counts = [];
        $executions = [];
        $total = 0;
        foreach (explode("\n", $data) as $line) {
            $line = trim($line);
            if ($line === '') continue;
            try {
                $ev = json_decode($line, true, 512, JSON_THROW_ON_ERROR);
                $total++;
                if (isset($ev['kind'])) {
                    $k = (string) $ev['kind'];
                    $counts[$k] = ($counts[$k] ?? 0) + 1;
                }
                if (isset($ev['execution_id'])) {
                    $executions[(string) $ev['execution_id']] = true;
                }
            } catch (\Throwable) {}
        }
        echo "total events: $total\n";
        echo 'distinct executions: ' . count($executions) . "\n";
        arsort($counts);
        foreach ($counts as $k => $n) {
            printf("  %6d  %s\n", $n, $k);
        }
        return 0;
    }

    /** @param string[] $args */
    private static function cmdCoordinator(array $args): int
    {
        if (count($args) === 0 || $args[0] !== 'demo') {
            fwrite(STDERR, "usage: iaiso coordinator demo\n");
            return 2;
        }
        $c = SharedPressureCoordinator::builder()
            ->coordinatorId('cli-demo')
            ->escalationThreshold(1.5)
            ->releaseThreshold(2.5)
            ->notifyCooldownSeconds(0.0)
            ->aggregator(new SumAggregator())
            ->auditSink(new MemorySink())
            ->onEscalation(fn($s) => printf(
                "  [callback] ESCALATION at aggregate=%.3f\n", $s->aggregatePressure))
            ->onRelease(fn($s) => printf(
                "  [callback] RELEASE at aggregate=%.3f\n", $s->aggregatePressure))
            ->build();
        $workers = ['worker-a', 'worker-b', 'worker-c'];
        foreach ($workers as $w) $c->register($w);
        echo "Demo: 3 workers registered. Stepping pressures...\n";
        $steps = [0.3, 0.6, 0.9, 0.6];
        foreach ($steps as $i => $p) {
            foreach ($workers as $w) $c->update($w, $p);
            $snap = $c->snapshot();
            printf("  step %d: per-worker=%.2f  aggregate=%.3f  lifecycle=%s\n",
                $i + 1, $p, $snap->aggregatePressure, $snap->lifecycle->value);
        }
        return 0;
    }

    /** @param string[] $args */
    private static function cmdConformance(array $args): int
    {
        $specRoot = $args[0] ?? './spec';
        try {
            $r = ConformanceRunner::runAll($specRoot);
            $sections = [
                'pressure' => $r->pressure,
                'consent'  => $r->consent,
                'events'   => $r->events,
                'policy'   => $r->policy,
            ];
            $fail = 0;
            foreach ($sections as $name => $bucket) {
                $pass = 0;
                foreach ($bucket as $v) if ($v->passed) $pass++;
                $total = count($bucket);
                $tag = $pass === $total ? 'PASS' : 'FAIL';
                if ($pass !== $total) {
                    $fail += $total - $pass;
                    foreach ($bucket as $v) {
                        if (!$v->passed) {
                            echo "  [$name] {$v->name}: {$v->message}\n";
                        }
                    }
                }
                echo "[$tag] $name: $pass/$total\n";
            }
            echo "\nconformance: " . $r->countPassed() . '/' . $r->countTotal()
                . " vectors passed\n";
            return $fail > 0 ? 1 : 0;
        } catch (\Throwable $e) {
            fwrite(STDERR, 'error: ' . $e->getMessage() . "\n");
            return 1;
        }
    }
}
