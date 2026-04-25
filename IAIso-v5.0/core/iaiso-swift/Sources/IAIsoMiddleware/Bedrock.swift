import Foundation
import IAIsoCore

/// AWS Bedrock runtime middleware. Supports Converse API (preferred —
/// normalized usage extraction) and the lower-level InvokeModel API.
public enum Bedrock {

    public protocol Client {
        func converse(_ params: [String: Any]) throws -> ConverseResponse
        func invokeModel(_ params: [String: Any]) throws -> InvokeResponse
    }

    public struct ConverseUsage: Sendable, Equatable {
        public let inputTokens: Int64
        public let outputTokens: Int64
        public let totalTokens: Int64
        public init(
            inputTokens: Int64 = 0,
            outputTokens: Int64 = 0,
            totalTokens: Int64 = 0
        ) {
            self.inputTokens = inputTokens
            self.outputTokens = outputTokens
            self.totalTokens = totalTokens
        }
    }

    public struct ConverseContentBlock: Sendable, Equatable {
        public let hasToolUse: Bool
        public init(hasToolUse: Bool = false) { self.hasToolUse = hasToolUse }
    }

    public struct ConverseResponse: Sendable {
        public let usage: ConverseUsage
        public let content: [ConverseContentBlock]
        public init(usage: ConverseUsage, content: [ConverseContentBlock]) {
            self.usage = usage
            self.content = content
        }
    }

    public struct InvokeResponse: Sendable {
        public let modelId: String
        public let body: Data
        public init(modelId: String = "", body: Data = Data()) {
            self.modelId = modelId
            self.body = body
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

        public func converse(_ params: [String: Any]) throws -> ConverseResponse {
            try checkState()
            let resp: ConverseResponse
            do {
                resp = try raw.converse(params)
            } catch {
                throw MiddlewareError.provider(
                    error.localizedDescription, underlying: error)
            }
            var tokens = resp.usage.totalTokens
            if tokens == 0 {
                tokens = resp.usage.inputTokens + resp.usage.outputTokens
            }
            let toolCalls: Int64 = resp.content.reduce(0) { acc, b in
                acc + (b.hasToolUse ? 1 : 0)
            }
            let modelId = (params["modelId"] as? String) ?? "unknown"
            execution.recordStep(StepInput(
                tokens: tokens,
                toolCalls: toolCalls,
                tag: "bedrock.converse:\(modelId)"))
            return resp
        }

        public func invokeModel(_ params: [String: Any]) throws -> InvokeResponse {
            try checkState()
            let resp: InvokeResponse
            do {
                resp = try raw.invokeModel(params)
            } catch {
                throw MiddlewareError.provider(
                    error.localizedDescription, underlying: error)
            }
            let modelId = !resp.modelId.isEmpty
                ? resp.modelId : ((params["modelId"] as? String) ?? "unknown")
            execution.recordStep(StepInput(tag: "bedrock.invokeModel:\(modelId)"))
            return resp
        }

        private func checkState() throws {
            let pre = execution.check()
            if pre == .locked { throw MiddlewareError.locked }
            if pre == .escalated, opts.raiseOnEscalation {
                throw MiddlewareError.escalationRaised
            }
        }
    }
}
