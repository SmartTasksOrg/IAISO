<?php

declare(strict_types=1);

namespace IAIso\Audit;

/**
 * IAIso audit event envelope.
 *
 * The JSON form of this object MUST emit fields in spec order:
 * schema_version, execution_id, kind, timestamp, data — with `data`
 * keys sorted alphabetically. Integer-valued floats serialize as
 * `0` not `0.0` to match the wire format of every other reference SDK.
 */
final class Event
{
    public const CURRENT_SCHEMA_VERSION = '1.0';

    public function __construct(
        public readonly string $executionId,
        public readonly string $kind,
        public readonly float $timestamp,
        public readonly array $data = [],
        public readonly string $schemaVersion = self::CURRENT_SCHEMA_VERSION,
    ) {
    }

    /**
     * Serialize to canonical JSON. Field order: schema_version,
     * execution_id, kind, timestamp, data. `data` keys sorted
     * alphabetically. Numbers without a fractional part emit as
     * integer literals.
     */
    public function toJson(): string
    {
        $parts = [];
        $parts[] = '"schema_version":' . self::encodeScalar($this->schemaVersion);
        $parts[] = '"execution_id":' . self::encodeScalar($this->executionId);
        $parts[] = '"kind":' . self::encodeScalar($this->kind);
        $parts[] = '"timestamp":' . self::encodeNumber($this->timestamp);
        $parts[] = '"data":' . self::encodeMap($this->data);
        return '{' . implode(',', $parts) . '}';
    }

    /**
     * Encode a value with our spec's number-formatting rules.
     */
    public static function encodeValue(mixed $v): string
    {
        if ($v === null) return 'null';
        if (is_bool($v)) return $v ? 'true' : 'false';
        if (is_int($v) || is_float($v)) return self::encodeNumber($v);
        if (is_string($v)) return self::encodeScalar($v);
        if (is_array($v)) {
            // Distinguish list vs map: list = sequential 0..n-1
            if (array_is_list($v)) {
                $items = array_map(fn($x) => self::encodeValue($x), $v);
                return '[' . implode(',', $items) . ']';
            }
            return self::encodeMap($v);
        }
        // Fallback: stringify
        return json_encode((string) $v, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    }

    private static function encodeMap(array $m): string
    {
        // Stable sort keys alphabetically for spec compliance.
        ksort($m, SORT_STRING);
        $parts = [];
        foreach ($m as $k => $v) {
            $parts[] = self::encodeScalar((string) $k) . ':' . self::encodeValue($v);
        }
        return '{' . implode(',', $parts) . '}';
    }

    private static function encodeScalar(string $s): string
    {
        // json_encode handles full UTF-8 + escaping correctly.
        return json_encode($s, JSON_UNESCAPED_SLASHES | JSON_UNESCAPED_UNICODE);
    }

    /**
     * Format a number — integer-valued floats serialize as integers
     * to match the wire format of the other reference SDKs.
     */
    private static function encodeNumber(int|float $n): string
    {
        if (is_int($n)) {
            return (string) $n;
        }
        if (is_nan($n) || is_infinite($n)) {
            // JSON cannot represent these — emit null.
            return 'null';
        }
        // Integer-valued float: emit as integer.
        if (floor($n) === $n && abs($n) < 1e16) {
            return (string) (int) $n;
        }
        // Use PHP's default float formatting (handles precision sensibly).
        $s = (string) $n;
        // Make sure scientific notation uses the canonical lowercase form.
        if (str_contains($s, 'E')) {
            $s = str_replace('E', 'e', $s);
        }
        return $s;
    }
}
