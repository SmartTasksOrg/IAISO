using System.Collections.Generic;
using System.Globalization;
using System.Text;
using System.Text.Encodings.Web;
using System.Text.Json;

namespace Iaiso.Audit;

/// <summary>
/// A canonical IAIso audit event.
/// </summary>
/// <remarks>
/// The JSON serialization writes fields in the spec-mandated order:
/// <c>schema_version, execution_id, kind, timestamp, data</c>. The
/// <c>data</c> map's keys are sorted alphabetically (via
/// <see cref="SortedDictionary{TKey, TValue}"/>) so identical inputs
/// produce byte-identical output across runs and across all reference
/// SDKs.
/// </remarks>
public sealed class Event
{
    /// <summary>Current audit envelope schema version.</summary>
    public const string CurrentSchemaVersion = "1.0";

    private static readonly JsonSerializerOptions JsonOpts = new()
    {
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping,
        NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.Strict,
    };

    public string SchemaVersion { get; }
    public string ExecutionId { get; }
    public string Kind { get; }
    public double Timestamp { get; }
    public IReadOnlyDictionary<string, object?> Data { get; }

    public Event(string executionId, string kind, double timestamp,
                 IReadOnlyDictionary<string, object?>? data)
    {
        SchemaVersion = CurrentSchemaVersion;
        ExecutionId = executionId;
        Kind = kind;
        Timestamp = timestamp;
        // Preserve sorted-key order for stable serialization
        Data = data is null
            ? new SortedDictionary<string, object?>()
            : new SortedDictionary<string, object?>(new Dictionary<string, object?>(data));
    }

    /// <summary>
    /// Serialize to JSON in the spec-mandated key order.
    /// </summary>
    public string ToJson()
    {
        var sb = new StringBuilder();
        sb.Append('{');
        sb.Append("\"schema_version\":").Append(JsonSerializer.Serialize(SchemaVersion, JsonOpts));
        sb.Append(",\"execution_id\":").Append(JsonSerializer.Serialize(ExecutionId, JsonOpts));
        sb.Append(",\"kind\":").Append(JsonSerializer.Serialize(Kind, JsonOpts));
        sb.Append(",\"timestamp\":").Append(FormatNumber(Timestamp));
        sb.Append(",\"data\":").Append(SerializeData(Data));
        sb.Append('}');
        return sb.ToString();
    }

    public override string ToString() => ToJson();

    /// <summary>
    /// Format a double the way the other reference SDKs do:
    /// integers as <c>0</c>, <c>1700000000</c> (no trailing decimals),
    /// non-integers with their natural representation.
    /// </summary>
    internal static string FormatNumber(double d)
    {
        if (double.IsFinite(d) && d == System.Math.Floor(d))
        {
            long asLong = (long)d;
            if ((double)asLong == d)
            {
                return asLong.ToString(CultureInfo.InvariantCulture);
            }
        }
        return d.ToString("R", CultureInfo.InvariantCulture);
    }

    /// <summary>
    /// Serialize the data payload — keys sorted, numbers formatted
    /// consistently with the timestamp.
    /// </summary>
    internal static string SerializeData(IReadOnlyDictionary<string, object?> data)
    {
        var sb = new StringBuilder();
        sb.Append('{');
        bool first = true;
        foreach (var kv in data)
        {
            if (!first) sb.Append(',');
            first = false;
            sb.Append(JsonSerializer.Serialize(kv.Key, JsonOpts));
            sb.Append(':');
            sb.Append(SerializeValue(kv.Value));
        }
        sb.Append('}');
        return sb.ToString();
    }

    private static string SerializeValue(object? v)
    {
        return v switch
        {
            null => "null",
            bool b => b ? "true" : "false",
            string s => JsonSerializer.Serialize(s, JsonOpts),
            double d => FormatNumber(d),
            float f => FormatNumber(f),
            long l => l.ToString(CultureInfo.InvariantCulture),
            int i => i.ToString(CultureInfo.InvariantCulture),
            short sh => sh.ToString(CultureInfo.InvariantCulture),
            byte by => by.ToString(CultureInfo.InvariantCulture),
            IReadOnlyDictionary<string, object?> sub => SerializeData(sub),
            IDictionary<string, object?> sub2 => SerializeData(
                new SortedDictionary<string, object?>(new Dictionary<string, object?>(sub2))),
            IEnumerable<object?> arr => SerializeArray(arr),
            _ => JsonSerializer.Serialize(v, JsonOpts),
        };
    }

    private static string SerializeArray(IEnumerable<object?> arr)
    {
        var sb = new StringBuilder();
        sb.Append('[');
        bool first = true;
        foreach (var item in arr)
        {
            if (!first) sb.Append(',');
            first = false;
            sb.Append(SerializeValue(item));
        }
        sb.Append(']');
        return sb.ToString();
    }
}
