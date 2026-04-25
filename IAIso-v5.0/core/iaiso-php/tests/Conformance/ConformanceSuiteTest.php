<?php

declare(strict_types=1);

namespace IAIso\Tests\Conformance;

use IAIso\Conformance\ConformanceRunner;
use PHPUnit\Framework\TestCase;

final class ConformanceSuiteTest extends TestCase
{
    public function testAllVectorsPass(): void
    {
        $r = ConformanceRunner::runAll(__DIR__ . '/../../spec');
        $failures = '';
        foreach ([$r->pressure, $r->consent, $r->events, $r->policy] as $bucket) {
            foreach ($bucket as $v) {
                if (!$v->passed) {
                    $failures .= "\n  [{$v->section}] {$v->name}: {$v->message}";
                }
            }
        }
        $passed = $r->countPassed();
        $total = $r->countTotal();
        self::assertSame(67, $total, 'expected 67 total vectors');
        self::assertSame(0, $total - $passed,
            "conformance $passed/$total — failures:" . $failures);
    }
}
