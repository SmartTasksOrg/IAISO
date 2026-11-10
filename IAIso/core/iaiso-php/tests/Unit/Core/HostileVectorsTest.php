<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Core;

use IAIso\Audit\MemorySink;
use IAIso\Core\EngineOptions;
use IAIso\Core\PressureConfig;
use IAIso\Core\PressureEngine;
use IAIso\Core\ScriptedClock;
use IAIso\Core\StepInput;
use PHPUnit\Framework\TestCase;

/** spec/pressure/hostile.json is shared by every IAIso port. */
final class HostileVectorsTest extends TestCase
{
    /** @return array<string, mixed> */
    public static function hostile(): array
    {
        $raw = file_get_contents(__DIR__ . '/../../../spec/pressure/hostile.json');
        return json_decode((string) $raw, true, 512, JSON_THROW_ON_ERROR);
    }

    private static function engine(): PressureEngine
    {
        $clk = new ScriptedClock([0.0]);
        return new PressureEngine(PressureConfig::defaults(), new EngineOptions('hostile', new MemorySink(), $clk, $clk));
    }

    /** @return iterable<string, array{string, mixed}> */
    public static function rejects(): iterable
    {
        foreach (self::hostile()['reject'] as $v) {
            yield $v['name'] => [$v['field'], $v['value']];
        }
    }

    /** @dataProvider rejects */
    public function testHostileValueIsRefused(string $field, mixed $value): void
    {
        $this->expectException(\InvalidArgumentException::class);
        self::engine()->step(StepInput::fromArray([$field => $value]));
    }

    public function testConstructorRefusesNegatives(): void
    {
        $this->expectException(\InvalidArgumentException::class);
        new StepInput(tokens: -40000);
    }

    public function testExtremeValuesAreHandled(): void
    {
        foreach (self::hostile()['accept'] as $v) {
            $e = self::engine();
            $out = $e->step(StepInput::fromArray($v['step']));
            self::assertFalse(is_nan($e->getPressure()), $v['name']);
            self::assertEqualsWithDelta($v['expect']['pressure'], $e->getPressure(), 1e-9, $v['name']);
            self::assertSame($v['expect']['outcome'], $out->value, $v['name']);
            self::assertSame($v['expect']['lifecycle'], $e->getLifecycle()->value, $v['name']);
        }
    }
}
