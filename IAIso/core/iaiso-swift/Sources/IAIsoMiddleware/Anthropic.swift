import Foundation
import IAIsoCore

/// Anthropic Messages API middleware.
public enum Anthropic {

    /// Structural client interface — one method per Anthropic operation.
    public protocol Client {
        func messagesCreate(_ params: [String: Any]) throws -> Response
    }

    public struct ContentBlock: Sendable, Equatable {
        public let type: String
        public init(type: String) { self.type = type }
    }

    public struct Response: Sendable {
        public let model: String
        public let inputTokens: Int64
        public let outputTokens: Int64
        public let content: [ContentBlock]

        public init(
            model: String,
            inputTokens: Int64,
            outputTokens: Int64,
            content: [ContentBlock]
        ) {
            self.model = model
            self.inputTokens = inputTokens
            self.outputTokens = outputTokens
            self.content = content
        }
    }

    public struct Options: Sendable {
        public var raiseOnEscalation: Bool
        public init(raiseOnEscalation: Bool = false) {
            self.raiseOnEscalation = raiseOnEscalation
        }
        public static let defaults = Options()
    }

    /// Wraps a `Client` so every call is accounted against a `BoundedExecution`.
    public final class BoundedClient {
        private let raw: Client
        private let execution: BoundedExecution
        private let opts: Options

        public init(raw: Client, execution: BoundedExecution, options: Options = .defaults) {
            self.raw = raw
            self.execution = execution
            self.opts = options
        }

        public func messagesCreate(_ params: [String: Any]) throws -> Response {
            let pre = execution.check()
            if pre == .locked { throw MiddlewareError.locked }
            if pre == .escalated, opts.raiseOnEscalation {
                throw MiddlewareError.escalationRaised
            }
            let resp: Response
            do {
                resp = try raw.messagesCreate(params)
            } catch {
                throw MiddlewareError.provider(
                    error.localizedDescription, underlying: error)
            }
            let tokens = resp.inputTokens + resp.outputTokens
            let toolCalls: Int64 = resp.content.reduce(0) { acc, b in
                acc + (b.type == "tool_use" ? 1 : 0)
            }
            let model = resp.model.isEmpty ? "unknown" : resp.model
            execution.recordStep(StepInput(
                tokens: tokens,
                toolCalls: toolCalls,
                tag: "anthropic.messages.create:\(model)"))
            return resp
        }
    }
}
