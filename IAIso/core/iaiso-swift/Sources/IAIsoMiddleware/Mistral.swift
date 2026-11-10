import Foundation
import IAIsoCore

/// Mistral chat middleware.
public enum Mistral {

    public protocol Client {
        func chatComplete(_ params: [String: Any]) throws -> Response
    }

    public struct Usage: Sendable, Equatable {
        public let promptTokens: Int64
        public let completionTokens: Int64
        public let totalTokens: Int64
        public init(
            promptTokens: Int64 = 0,
            completionTokens: Int64 = 0,
            totalTokens: Int64 = 0
        ) {
            self.promptTokens = promptTokens
            self.completionTokens = completionTokens
            self.totalTokens = totalTokens
        }
    }

    public struct Choice: Sendable {
        public let toolCalls: [String]
        public init(toolCalls: [String] = []) { self.toolCalls = toolCalls }
    }

    public struct Response: Sendable {
        public let model: String
        public let usage: Usage
        public let choices: [Choice]
        public init(model: String, usage: Usage, choices: [Choice]) {
            self.model = model
            self.usage = usage
            self.choices = choices
        }
    }

    public struct Options: Sendable {
        public var raiseOnEscalation: Bool
        public init(raiseOnEscalation: Bool = false) {
            self.raiseOnEscalation = raiseOnEscalation
        }
        public static let defaults = Options()
    }

    public final class BoundedClient {
        private let raw: Client
        private let execution: BoundedExecution
        private let opts: Options

        public init(raw: Client, execution: BoundedExecution, options: Options = .defaults) {
            self.raw = raw
            self.execution = execution
            self.opts = options
        }

        public func chatComplete(_ params: [String: Any]) throws -> Response {
            let pre = execution.check()
            if pre == .locked { throw MiddlewareError.locked }
            if pre == .escalated, opts.raiseOnEscalation {
                throw MiddlewareError.escalationRaised
            }
            let resp: Response
            do {
                resp = try raw.chatComplete(params)
            } catch {
                throw MiddlewareError.provider(
                    error.localizedDescription, underlying: error)
            }
            var tokens = resp.usage.totalTokens
            if tokens == 0 {
                tokens = resp.usage.promptTokens + resp.usage.completionTokens
            }
            let toolCalls: Int64 = resp.choices.reduce(0) { acc, c in
                acc + Int64(c.toolCalls.count)
            }
            let model = resp.model.isEmpty ? "unknown" : resp.model
            execution.recordStep(StepInput(
                tokens: tokens,
                toolCalls: toolCalls,
                tag: "mistral.chat.complete:\(model)"))
            return resp
        }
    }
}
