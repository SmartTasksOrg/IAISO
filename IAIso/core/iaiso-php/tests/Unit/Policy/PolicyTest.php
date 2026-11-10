<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Policy;

use IAIso\Policy\MaxAggregator;
use IAIso\Policy\PolicyException;
use IAIso\Policy\PolicyLoader;
use IAIso\Policy\SumAggregator;
use IAIso\Policy\WeightedSumAggregator;
use PHPUnit\Framework\TestCase;

final class PolicyTest extends TestCase
{
    public function testBuildMinimalPolicy(): void
    {
        $p = PolicyLoader::build(['version' => '1']);
        self::assertSame('1', $p->version);
        self::assertSame('sum', $p->aggregator->name());
    }

    public function testBuildOverridesDefaults(): void
    {
        $p = PolicyLoader::build([
            'version' => '1',
            'pressure' => ['escalation_threshold' => 0.7, 'release_threshold' => 0.85],
            'coordinator' => ['aggregator' => 'max'],
        ]);
        self::assertEqualsWithDelta(0.7, $p->pressure->escalationThreshold, 1e-9);
        self::assertSame('max', $p->aggregator->name());
    }

    public function testRejectsMissingVersion(): void
    {
        $this->expectException(PolicyException::class);
        $this->expectExceptionMessageMatches('/version/');
        // Use stdClass-like associative array so it's seen as a mapping
        // but with no `version` key.
        PolicyLoader::build(['metadata' => ['note' => 'no version here']]);
    }

    public function testRejectsBadVersion(): void
    {
        $this->expectException(PolicyException::class);
        PolicyLoader::build(['version' => '2']);
    }

    public function testRejectsReleaseBelowEscalation(): void
    {
        $this->expectException(PolicyException::class);
        PolicyLoader::build([
            'version' => '1',
            'pressure' => ['escalation_threshold' => 0.9, 'release_threshold' => 0.5],
        ]);
    }

    public function testRejectsStringAsNumber(): void
    {
        // The strict-typing gotcha: string "0.015" should NOT validate as a number.
        $this->expectException(PolicyException::class);
        PolicyLoader::build([
            'version' => '1',
            'pressure' => ['token_coefficient' => '0.015'],
        ]);
    }

    public function testSumAggregator(): void
    {
        self::assertEqualsWithDelta(
            0.8, (new SumAggregator())->aggregate(['a' => 0.3, 'b' => 0.5]), 1e-9);
    }

    public function testMaxAggregator(): void
    {
        self::assertEqualsWithDelta(
            0.5, (new MaxAggregator())->aggregate(['a' => 0.3, 'b' => 0.5]), 1e-9);
    }

    public function testWeightedSumAggregator(): void
    {
        $a = new WeightedSumAggregator(['important' => 2.0], 1.0);
        self::assertEqualsWithDelta(
            1.3, $a->aggregate(['important' => 0.5, 'normal' => 0.3]), 1e-9);
    }
}
