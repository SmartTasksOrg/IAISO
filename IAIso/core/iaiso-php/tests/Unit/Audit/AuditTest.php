<?php

declare(strict_types=1);

namespace IAIso\Tests\Unit\Audit;

use IAIso\Audit\Event;
use IAIso\Audit\FanoutSink;
use IAIso\Audit\JsonlFileSink;
use IAIso\Audit\MemorySink;
use IAIso\Audit\NullSink;
use PHPUnit\Framework\TestCase;

final class AuditTest extends TestCase
{
    public function testEventEmitsFieldsInSpecOrder(): void
    {
        $e = new Event('exec-1', 'engine.init', 0.0, ['pressure' => 0.0]);
        $json = $e->toJson();
        // schema_version, execution_id, kind, timestamp, data
        self::assertStringStartsWith('{"schema_version":', $json);
        self::assertStringContainsString('"execution_id":"exec-1"', $json);
        $svPos = strpos($json, '"schema_version"');
        $eiPos = strpos($json, '"execution_id"');
        $knPos = strpos($json, '"kind"');
        $tsPos = strpos($json, '"timestamp"');
        $dtPos = strpos($json, '"data"');
        self::assertLessThan($eiPos, $svPos);
        self::assertLessThan($knPos, $eiPos);
        self::assertLessThan($tsPos, $knPos);
        self::assertLessThan($dtPos, $tsPos);
    }

    public function testIntegerFloatsSerializeAsIntegers(): void
    {
        $e = new Event('e', 'k', 0.0, ['n' => 0.0]);
        $json = $e->toJson();
        // 0.0 should appear as 0, not 0.0
        self::assertStringContainsString('"timestamp":0', $json);
        self::assertStringNotContainsString('"timestamp":0.0', $json);
        self::assertStringContainsString('"n":0', $json);
        self::assertStringNotContainsString('"n":0.0', $json);
    }

    public function testDataKeysSortedAlphabetically(): void
    {
        $e = new Event('e', 'k', 0.0, ['z' => 1, 'a' => 2, 'm' => 3]);
        $json = $e->toJson();
        $aPos = strpos($json, '"a"');
        $mPos = strpos($json, '"m"');
        $zPos = strpos($json, '"z"');
        self::assertLessThan($mPos, $aPos);
        self::assertLessThan($zPos, $mPos);
    }

    public function testNullDataValuesEmit(): void
    {
        $e = new Event('e', 'k', 0.0, ['tag' => null]);
        $json = $e->toJson();
        self::assertStringContainsString('"tag":null', $json);
    }

    public function testMemorySinkStoresEvents(): void
    {
        $sink = new MemorySink();
        $sink->emit(new Event('e', 'a', 0.0, []));
        $sink->emit(new Event('e', 'b', 0.0, []));
        self::assertCount(2, $sink->events());
        self::assertSame('a', $sink->events()[0]->kind);
    }

    public function testFanoutSinkBroadcasts(): void
    {
        $a = new MemorySink();
        $b = new MemorySink();
        $f = new FanoutSink($a, $b);
        $f->emit(new Event('e', 'k', 0.0, []));
        self::assertCount(1, $a->events());
        self::assertCount(1, $b->events());
    }

    public function testJsonlFileSinkAppends(): void
    {
        $path = tempnam(sys_get_temp_dir(), 'iaiso-audit-');
        $sink = new JsonlFileSink($path);
        $sink->emit(new Event('e', 'a', 0.0, []));
        $sink->emit(new Event('e', 'b', 0.0, []));
        $contents = file_get_contents($path);
        unlink($path);
        $lines = array_filter(explode("\n", $contents));
        self::assertCount(2, $lines);
        foreach ($lines as $line) {
            $obj = json_decode($line, true);
            self::assertIsArray($obj);
            self::assertArrayHasKey('schema_version', $obj);
        }
    }

    public function testNullSinkSwallowsEvents(): void
    {
        // Just confirms it doesn't blow up
        NullSink::instance()->emit(new Event('e', 'k', 0.0, []));
        self::assertTrue(true);
    }
}
