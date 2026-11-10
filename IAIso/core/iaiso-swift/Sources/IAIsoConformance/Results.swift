import Foundation

public struct VectorResult: Sendable {
    public let section: String
    public let name: String
    public let passed: Bool
    public let message: String

    public init(section: String, name: String, passed: Bool, message: String = "") {
        self.section = section
        self.name = name
        self.passed = passed
        self.message = message
    }

    public static func pass(_ section: String, _ name: String) -> VectorResult {
        return VectorResult(section: section, name: name, passed: true)
    }

    public static func fail(_ section: String, _ name: String, _ msg: String) -> VectorResult {
        return VectorResult(section: section, name: name, passed: false, message: msg)
    }
}

public struct SectionResults: Sendable {
    public var pressure: [VectorResult] = []
    public var consent: [VectorResult] = []
    public var events: [VectorResult] = []
    public var policy: [VectorResult] = []

    public init() {}

    public func countPassed() -> Int {
        var n = 0
        for r in pressure where r.passed { n += 1 }
        for r in consent where r.passed { n += 1 }
        for r in events where r.passed { n += 1 }
        for r in policy where r.passed { n += 1 }
        return n
    }

    public func countTotal() -> Int {
        return pressure.count + consent.count + events.count + policy.count
    }
}
