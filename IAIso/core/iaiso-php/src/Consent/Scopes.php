<?php

declare(strict_types=1);

namespace IAIso\Consent;

/** Scope-matching logic. */
final class Scopes
{
    private function __construct() {}

    /**
     * Return true iff the {@code requested} scope is granted by any
     * scope in {@code granted}. Match rules per
     * {@code spec/consent/README.md}:
     *
     * <ul>
     *   <li>Exact match: granted "tools.search" satisfies requested "tools.search".</li>
     *   <li>Prefix-at-segment-boundary: granted "tools" satisfies requested "tools.search"
     *       (boundary is the dot).</li>
     *   <li>Substring without boundary does NOT match: "tools" does not satisfy "toolsbar".</li>
     *   <li>More specific does NOT satisfy less specific: "tools.search.bulk"
     *       does not satisfy "tools.search".</li>
     * </ul>
     *
     * @param string[] $granted
     * @throws \InvalidArgumentException if {@code $requested} is empty
     */
    public static function granted(array $granted, string $requested): bool
    {
        if ($requested === '') {
            throw new \InvalidArgumentException('requested scope must be non-empty');
        }
        foreach ($granted as $g) {
            if ($g === $requested) {
                return true;
            }
            // Prefix at boundary: $g . '.' must be a prefix of $requested
            $prefixWithDot = $g . '.';
            if (str_starts_with($requested, $prefixWithDot)) {
                return true;
            }
        }
        return false;
    }
}
