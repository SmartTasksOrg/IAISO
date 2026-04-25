import Foundation
import IAIsoCore

/// OpenAI Chat Completions middleware. Also works for any
/// OpenAI-compatible endpoint (Azure OpenAI, vLLM, TGI, LiteLLM proxy,
/// Together, Groq, etc.).
public enum OpenAI {

    public protocol Client {
        func chatCompletionsCreate(_ params: [String: Any]) throws -> Response
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

    public struct ToolCall: Sendable, Equatable {
        public let id: String
        public init(id: String) { self.id = id }
    }

    public struct Choice: Sendable {
        public let toolCalls: [ToolCall]
        public let hasFunctionCall: Bool
        public init(toolCalls: [ToolCall] = [], hasFunctionCall: Bool = false) {
            self.toolCalls = toolCalls
            self.hasFunctionCall = hasFunctionCall
        }
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

        public func chatCompletionsCreate(_ params: [String: Any]) throws -> Response {
            let pre = execution.check()
            if pre == .locked { throw MiddlewareError.locked }
            if pre == .escalated, opts.raiseOnEscalation {
                throw MiddlewareError.escalationRaised
            }
            let resp: Response
            do {
                resp = try raw.chatCompletionsCreate(params)
            } catch {
                throw MiddlewareError.provider(
                    error.localizedDescription, underlying: error)
            }
            var tokens = resp.usage.totalTokens
            if tokens == 0 {
                tokens = resp.usage.promptTokens + resp.usage.completionTokens
            }
            var toolCalls: Int64 = 0
            for c in resp.choices {
                toolCalls += Int64(c.toolCalls.count)
                if c.hasFunctionCall { toolCalls += 1 }
            }
            let model = resp.model.isEmpty ? "unknown" : resp.model
            execution.recordStep(StepInput(
                tokens: tokens,
                toolCalls: toolCalls,
                tag: "openai.chat.completions.create:\(model)"))
            return resp
        }
    }
}
