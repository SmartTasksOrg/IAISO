<?php

declare(strict_types=1);

namespace IAIso\Conformance;

/** Top-level conformance runner. */
final class ConformanceRunner
{
    private function __construct() {}

    /** Run every section against the spec at {@code $specRoot}. */
    public static function runAll(string $specRoot): SectionResults
    {
        $r = new SectionResults();
        $r->pressure = PressureRunner::run($specRoot);
        $r->consent  = ConsentRunner::run($specRoot);
        $r->events   = EventsRunner::run($specRoot);
        $r->policy   = PolicyRunner::run($specRoot);
        return $r;
    }
}
