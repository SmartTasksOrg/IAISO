import Foundation
import IAIsoCore

/// Cohere chat middleware.
public enum Cohere {

    public protocol Client {
        func chat(_ params: [String: Any]) throws -> Response
    }

    public struct BilledUnits: Sendable, Equatable {
        public let inputTokens: Int64
        public let outputTokens: Int64
        public init(inputTokens: Int64 = 0, outputTokens: Int64 = 0) {
            self.inputTokens = inputTokens
            self.outputTokens = outputTokens
        }
    }

    public struct Meta: Sendable, Equatable {
        public let tokens: BilledUnits?
        public let billedUnits: BilledUnits?
        public init(tokens: BilledUnits? = nil, billedUnits: BilledUnits? = nil) {
            self.tokens = tokens
            self.billedUnits = billedUnits
        }
    }

    public struct ToolCall: Sendable, Equatable {
        public let name: String
        public init(name: String) { self.name = name }
    }

    public struct Response: Sendable {
        public let model: String
        public let meta: Meta
        public let toolCalls: [ToolCall]
        public init(model: String, meta: Meta, toolCalls: [ToolCall] = []) {
            self.model = model
            self.meta = meta
            self.toolCalls = toolCalls
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

        public func chat(_ params: [String: Any]) throws -> Response {
            let pre = execution.check()
            if pre == .locked { throw MiddlewareError.locked }
            if pre == .escalated, opts.raiseOnEscalation {
                throw MiddlewareError.escalationRaised
            }
            let resp: Response
            do {
                resp = try raw.chat(params)
            } catch {
                throw MiddlewareError.provider(
                    error.localizedDescription, underlying: error)
            }
            let units = resp.meta.tokens ?? resp.meta.billedUnits
            let tokens = (units != nil)
                ? (units!.inputTokens + units!.outputTokens) : 0
            let toolCalls = Int64(resp.toolCalls.count)
            let model = resp.model.isEmpty ? "unknown" : resp.model
            execution.recordStep(StepInput(
                tokens: tokens,
                toolCalls: toolCalls,
                tag: "cohere.chat:\(model)"))
            return resp
        }
    }
}
