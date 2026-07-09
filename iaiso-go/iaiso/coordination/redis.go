package coordination

import (
	"context"
	"crypto/sha1"
	"encoding/hex"
	"fmt"
	"sort"
	"strconv"
	"sync"
	"time"

	"github.com/iaiso/iaiso-go/iaiso/audit"
	"github.com/iaiso/iaiso-go/iaiso/policy"
	goredis "github.com/redis/go-redis/v9"
)

func defaultClock() float64 { return float64(time.Now().UnixNano()) / 1e9 }

// UpdateAndFetchScript is verbatim from spec/coordinator/README.md §1.2.
// Every port executes this exact source, so the SHA is identical across
// languages and EVALSHA hits the same cached script.
const UpdateAndFetchScript = `-- KEYS[1]: the pressures hash key
-- ARGV[1]: execution_id
-- ARGV[2]: new pressure as a string
-- ARGV[3]: TTL in integer seconds; 0 to skip

local pressures_key = KEYS[1]
local exec_id       = ARGV[1]
local new_pressure  = ARGV[2]
local ttl_seconds   = tonumber(ARGV[3])

redis.call('HSET', pressures_key, exec_id, new_pressure)
if ttl_seconds > 0 then
  redis.call('EXPIRE', pressures_key, ttl_seconds)
end

return redis.call('HGETALL', pressures_key)
`

// ScriptSHA is the SHA-1 digest Redis assigns to UpdateAndFetchScript.
func ScriptSHA() string {
	sum := sha1.Sum([]byte(UpdateAndFetchScript))
	return hex.EncodeToString(sum[:])
}

// DefaultKeyPrefix per spec/coordinator/README.md §1.
const DefaultKeyPrefix = "iaiso:coord"

// RedisClient is the narrow slice of Redis this package needs. Keeping it
// structural means the coordinator is testable without a server, and
// operators can plug in any client. Adapt *redis.Client with FromGoRedis.
type RedisClient interface {
	// EvalSha runs a preloaded script; Eval runs the source. Implementations
	// may fall back from EvalSha to Eval on NOSCRIPT.
	Eval(ctx context.Context, script string, keys []string, args ...any) (any, error)
	EvalSha(ctx context.Context, sha string, keys []string, args ...any) (any, error)
	ScriptLoad(ctx context.Context, script string) (string, error)
	HGetAll(ctx context.Context, key string) (map[string]string, error)
	HKeys(ctx context.Context, key string) ([]string, error)
	HSet(ctx context.Context, key string, values ...any) error
}

type goRedisAdapter struct{ c goredis.UniversalClient }

// FromGoRedis adapts a github.com/redis/go-redis/v9 client.
func FromGoRedis(c goredis.UniversalClient) RedisClient { return &goRedisAdapter{c: c} }

func (a *goRedisAdapter) Eval(ctx context.Context, script string, keys []string, args ...any) (any, error) {
	return a.c.Eval(ctx, script, keys, args...).Result()
}
func (a *goRedisAdapter) EvalSha(ctx context.Context, sha string, keys []string, args ...any) (any, error) {
	return a.c.EvalSha(ctx, sha, keys, args...).Result()
}
func (a *goRedisAdapter) ScriptLoad(ctx context.Context, script string) (string, error) {
	return a.c.ScriptLoad(ctx, script).Result()
}
func (a *goRedisAdapter) HGetAll(ctx context.Context, key string) (map[string]string, error) {
	return a.c.HGetAll(ctx, key).Result()
}
func (a *goRedisAdapter) HKeys(ctx context.Context, key string) ([]string, error) {
	return a.c.HKeys(ctx, key).Result()
}
func (a *goRedisAdapter) HSet(ctx context.Context, key string, values ...any) error {
	return a.c.HSet(ctx, key, values...).Err()
}

// RedisCoordinatorOptions configures a RedisCoordinator.
type RedisCoordinatorOptions struct {
	Redis               RedisClient
	CoordinatorID       string
	KeyPrefix           string
	EscalationThreshold float64
	ReleaseThreshold    float64
	Aggregator          policy.Aggregator
	Callbacks           Callbacks
	Sink                audit.Sink
	// TTLSeconds refreshes on every write. Zero means the hash never
	// expires — set it explicitly if you want state to survive restarts.
	TTLSeconds int
	Clock      func() float64
}

// RedisCoordinator shares fleet pressure through Redis. It is interoperable
// with the Python, Node and Rust coordinators pointed at the same
// (KeyPrefix, CoordinatorID) tuple.
type RedisCoordinator struct {
	rdb        RedisClient
	id         string
	prefix     string
	escalation float64
	release    float64
	agg        policy.Aggregator
	cb         Callbacks
	sink       audit.Sink
	ttl        int
	clock      func() float64

	mu        sync.Mutex
	sha       string
	escalated bool
}

// NewRedisCoordinator validates options and preloads the Lua script. A
// ScriptLoad failure is not fatal: the coordinator falls back to EVAL.
func NewRedisCoordinator(ctx context.Context, opts RedisCoordinatorOptions) (*RedisCoordinator, error) {
	if opts.Redis == nil {
		return nil, fmt.Errorf("coordination: Redis client is required")
	}
	if opts.CoordinatorID == "" {
		opts.CoordinatorID = "default"
	}
	if opts.KeyPrefix == "" {
		opts.KeyPrefix = DefaultKeyPrefix
	}
	if opts.EscalationThreshold == 0 && opts.ReleaseThreshold == 0 {
		d := policy.DefaultCoordinatorConfig()
		opts.EscalationThreshold = d.EscalationThreshold
		opts.ReleaseThreshold = d.ReleaseThreshold
	}
	if opts.ReleaseThreshold <= opts.EscalationThreshold {
		return nil, fmt.Errorf(
			"coordination: release_threshold must exceed escalation_threshold (%v <= %v)",
			opts.ReleaseThreshold, opts.EscalationThreshold)
	}
	if opts.Aggregator == nil {
		opts.Aggregator = policy.SumAggregator{}
	}
	if opts.Sink == nil {
		opts.Sink = audit.NewNullSink()
	}
	if opts.Clock == nil {
		opts.Clock = defaultClock
	}
	c := &RedisCoordinator{
		rdb: opts.Redis, id: opts.CoordinatorID, prefix: opts.KeyPrefix,
		escalation: opts.EscalationThreshold, release: opts.ReleaseThreshold,
		agg: opts.Aggregator, cb: opts.Callbacks, sink: opts.Sink,
		ttl: opts.TTLSeconds, clock: opts.Clock,
	}
	if sha, err := opts.Redis.ScriptLoad(ctx, UpdateAndFetchScript); err == nil {
		c.sha = sha
	}
	return c, nil
}

// PressuresKey is the single key this coordinator touches:
// {prefix}:{id}:pressures. One key means no Redis Cluster slot routing.
func (c *RedisCoordinator) PressuresKey() string {
	return fmt.Sprintf("%s:%s:pressures", c.prefix, c.id)
}

// Register writes a zero pressure for executionID.
func (c *RedisCoordinator) Register(ctx context.Context, executionID string) error {
	return c.rdb.HSet(ctx, c.PressuresKey(), executionID, "0.0")
}

// Update atomically writes pressure and returns the post-write fleet view.
//
// HSET and HGETALL happen inside one Lua invocation, so no other client can
// observe the hash between them. Each worker reacts to the snapshot it saw.
func (c *RedisCoordinator) Update(ctx context.Context, executionID string, pressure float64) (Snapshot, error) {
	key := c.PressuresKey()
	args := []any{executionID, strconv.FormatFloat(pressure, 'g', -1, 64), c.ttl}

	var (
		raw any
		err error
	)
	c.mu.Lock()
	sha := c.sha
	c.mu.Unlock()

	if sha != "" {
		raw, err = c.rdb.EvalSha(ctx, sha, []string{key}, args...)
	}
	if sha == "" || err != nil {
		// EVALSHA is strictly a performance optimisation; EVAL is
		// semantically identical. Fall back on NOSCRIPT or any error.
		raw, err = c.rdb.Eval(ctx, UpdateAndFetchScript, []string{key}, args...)
		if err != nil {
			return Snapshot{}, fmt.Errorf("coordination: update failed: %w", err)
		}
	}

	pressures, err := parseHGetAll(raw)
	if err != nil {
		return Snapshot{}, err
	}
	return c.evaluate(ctx, pressures), nil
}

// Fetch reads the fleet view without writing.
func (c *RedisCoordinator) Fetch(ctx context.Context) (Snapshot, error) {
	m, err := c.rdb.HGetAll(ctx, c.PressuresKey())
	if err != nil {
		return Snapshot{}, fmt.Errorf("coordination: fetch failed: %w", err)
	}
	pressures := make(map[string]float64, len(m))
	for k, v := range m {
		f, err := strconv.ParseFloat(v, 64)
		if err != nil {
			return Snapshot{}, fmt.Errorf("coordination: bad float %q for %q: %w", v, k, err)
		}
		pressures[k] = f
	}
	return Snapshot{
		CoordinatorID: c.id,
		Aggregate:     c.agg.Aggregate(pressures),
		Pressures:     pressures,
	}, nil
}

// Reset sets every field to "0.0" without removing any, so active workers
// stay registered. Observable result per spec/coordinator/README.md §1.4.
func (c *RedisCoordinator) Reset(ctx context.Context) error {
	keys, err := c.rdb.HKeys(ctx, c.PressuresKey())
	if err != nil {
		return fmt.Errorf("coordination: reset failed: %w", err)
	}
	sort.Strings(keys)
	for _, k := range keys {
		if err := c.rdb.HSet(ctx, c.PressuresKey(), k, "0.0"); err != nil {
			return fmt.Errorf("coordination: reset failed: %w", err)
		}
	}
	c.mu.Lock()
	c.escalated = false
	c.mu.Unlock()
	c.emit("coordinator.reset", map[string]any{"aggregate": 0.0})
	return nil
}

func (c *RedisCoordinator) evaluate(ctx context.Context, pressures map[string]float64) Snapshot {
	snap := Snapshot{
		CoordinatorID: c.id,
		Aggregate:     c.agg.Aggregate(pressures),
		Pressures:     pressures,
	}
	c.mu.Lock()
	wasEscalated := c.escalated
	switch {
	case snap.Aggregate >= c.release:
		snap.Escalated, snap.Released = true, true
		c.escalated = false
	case snap.Aggregate >= c.escalation:
		snap.Escalated = true
		c.escalated = true
	default:
		c.escalated = false
	}
	c.mu.Unlock()

	if snap.Released {
		c.emit("coordinator.release", map[string]any{
			"aggregate": snap.Aggregate, "threshold": c.release,
		})
		_ = c.Reset(ctx)
		if c.cb.OnRelease != nil {
			c.cb.OnRelease(snap)
		}
	} else if snap.Escalated && !wasEscalated {
		c.emit("coordinator.escalation", map[string]any{
			"aggregate": snap.Aggregate, "threshold": c.escalation,
		})
		if c.cb.OnEscalation != nil {
			c.cb.OnEscalation(snap)
		}
	}
	return snap
}

func (c *RedisCoordinator) emit(kind string, data map[string]any) {
	c.sink.Emit(audit.NewEvent("redis-coord:"+c.id, kind, c.clock(), data))
}

// parseHGetAll reassembles the flat [field1, value1, field2, value2, ...]
// array the Lua script returns.
func parseHGetAll(raw any) (map[string]float64, error) {
	flat, ok := raw.([]any)
	if !ok {
		return nil, fmt.Errorf("coordination: expected HGETALL flat array, got %T", raw)
	}
	if len(flat)%2 != 0 {
		return nil, fmt.Errorf("coordination: HGETALL array has odd length %d", len(flat))
	}
	out := make(map[string]float64, len(flat)/2)
	for i := 0; i < len(flat); i += 2 {
		field := fmt.Sprint(flat[i])
		value := fmt.Sprint(flat[i+1])
		f, err := strconv.ParseFloat(value, 64)
		if err != nil {
			return nil, fmt.Errorf("coordination: bad float %q for %q: %w", value, field, err)
		}
		out[field] = f
	}
	return out, nil
}
