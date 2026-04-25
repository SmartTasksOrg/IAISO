import Foundation

/// Outcome of a single `PressureEngine.step()` call. The raw value is the wire form.
public enum StepOutcome: String, Sendable, CaseIterable {
    case ok = "ok"
    case escalated = "escalated"
    case released = "released"
    case locked = "locked"
}
