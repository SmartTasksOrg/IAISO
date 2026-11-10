<?php
// Runs spec/pressure/hostile.json without Composer or PHPUnit:
//   php tests/standalone/hostile.php
// The PHPUnit version is tests/Unit/Core/HostileVectorsTest.php.
declare(strict_types=1);

spl_autoload_register(static function (string $class): void {
    if (str_starts_with($class, 'IAIso\\')) {
        $f = __DIR__ . '/../../src/' . str_replace('\\', '/', substr($class, 6)) . '.php';
        if (is_file($f)) {
            require $f;
        }
    }
});

use IAIso\Audit\MemorySink;
use IAIso\Core\EngineOptions;
use IAIso\Core\PressureConfig;
use IAIso\Core\PressureEngine;
use IAIso\Core\ScriptedClock;
use IAIso\Core\StepInput;

$h = json_decode((string) file_get_contents(__DIR__ . '/../../spec/pressure/hostile.json'), true, 512, JSON_THROW_ON_ERROR);
$engine = static function (): PressureEngine {
    $clk = new ScriptedClock([0.0]);
    return new PressureEngine(PressureConfig::defaults(), new EngineOptions('hostile', new MemorySink(), $clk, $clk));
};
$fail = 0;
$n = 0;
foreach ($h['reject'] as $v) {
    $n++;
    try {
        $engine()->step(StepInput::fromArray([$v['field'] => $v['value']]));
        echo "FAIL {$v['name']}: accepted\n";
        $fail++;
    } catch (\InvalidArgumentException) {
    }
}
foreach ($h['accept'] as $v) {
    $n++;
    $e = $engine();
    $out = $e->step(StepInput::fromArray($v['step']));
    $ok = !is_nan($e->getPressure()) && abs($e->getPressure() - $v['expect']['pressure']) < 1e-9
        && $out->value === $v['expect']['outcome'] && $e->getLifecycle()->value === $v['expect']['lifecycle'];
    if (!$ok) {
        echo "FAIL {$v['name']}: {$e->getPressure()} {$out->value} {$e->getLifecycle()->value}\n";
        $fail++;
    }
}
try {
    new StepInput(tokens: -1);
    echo "FAIL constructor accepted -1\n";
    $fail++;
} catch (\InvalidArgumentException) {
}
echo "hostile: " . ($n - $fail) . "/{$n} passed\n";
exit($fail === 0 ? 0 : 1);
