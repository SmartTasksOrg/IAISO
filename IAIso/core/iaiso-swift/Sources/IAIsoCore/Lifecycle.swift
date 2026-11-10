import Foundation

/// Lifecycle states for a `PressureEngine`. The raw value is the wire form.
public enum Lifecycle: String, Sendable, CaseIterable {
    case `init` = "init"
    case running = "running"
    case escalated = "escalated"
    case released = "released"
    case locked = "locked"
}
