package iaiso

import "math"

type Engine struct {
    SystemID string
    Pressure float64
    BackProp bool
}

func NewEngine(id string) *Engine {
    return &Engine{SystemID: id, Pressure: 0.0, BackProp: true}
}

func (e *Engine) Update(tokens int, tools int) string {
    delta := (float64(tokens) * 0.00015) + (float64(tools) * 0.08)
    e.Pressure = math.Max(0, e.Pressure + delta - 0.02)

    if e.Pressure >= 0.95 {
        e.Pressure = 0.0
        return "RELEASE_TRIGGERED"
    }
    return "OK"
}
