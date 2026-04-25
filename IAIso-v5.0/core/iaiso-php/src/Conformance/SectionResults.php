<?php

declare(strict_types=1);

namespace IAIso\Conformance;

/** Results aggregated by section. */
final class SectionResults
{
    /** @var VectorResult[] */
    public array $pressure = [];
    /** @var VectorResult[] */
    public array $consent = [];
    /** @var VectorResult[] */
    public array $events = [];
    /** @var VectorResult[] */
    public array $policy = [];

    public function countPassed(): int
    {
        $n = 0;
        foreach ([$this->pressure, $this->consent, $this->events, $this->policy] as $bucket) {
            foreach ($bucket as $r) if ($r->passed) $n++;
        }
        return $n;
    }

    public function countTotal(): int
    {
        return count($this->pressure) + count($this->consent)
            + count($this->events) + count($this->policy);
    }
}
