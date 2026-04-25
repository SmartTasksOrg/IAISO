import XCTest
@testable import IAIsoAudit
@testable import IAIsoCore
@testable import IAIsoMiddleware

final class MiddlewareTests: XCTestCase {

    final class FakeAnthropic: Anthropic.Client {
        func messagesCreate(_ params: [String: Any]) throws -> Anthropic.Response {
            return Anthropic.Response(
                model: "claude-opus-4-7",
                inputTokens: 100, outputTokens: 250,
                content: [
                    Anthropic.ContentBlock(type: "text"),
                    Anthropic.ContentBlock(type: "tool_use"),
                    Anthropic.ContentBlock(type: "tool_use"),
                ])
        }
    }

    func testAccountsTokensAndToolCalls() throws {
        let sink = MemorySink()
        let exec = try BoundedExecution.start(.init(auditSink: sink))
        let client = Anthropic.BoundedClient(
            raw: FakeAnthropic(), execution: exec, options: .defaults)
        _ = try client.messagesCreate([:])

        var foundStep = false
        for e in sink.events where e.kind == "engine.step" {
            if let t = e.data["tokens"]?.intValue, t == 350,
               let tc = e.data["tool_calls"]?.intValue, tc == 2 {
                foundStep = true
            }
        }
        XCTAssertTrue(foundStep)
        exec.close()
    }

    func testRaisesOnEscalationWhenOptedIn() throws {
        let cfg = PressureConfig(
            depthCoefficient: 0.5,
            dissipationPerStep: 0.0,
            escalationThreshold: 0.4,
            releaseThreshold: 0.95)
        let exec = try BoundedExecution.start(.init(config: cfg))
        _ = exec.recordStep(StepInput(depth: 1)) // force escalation

        let client = Anthropic.BoundedClient(
            raw: FakeAnthropic(), execution: exec,
            options: Anthropic.Options(raiseOnEscalation: true))
        XCTAssertThrowsError(try client.messagesCreate([:])) { err in
            if case MiddlewareError.escalationRaised = err {
                // expected
            } else {
                XCTFail("expected escalationRaised, got \(err)")
            }
        }
    }
}
