import Foundation
import IAIsoCore

/// Google Gemini / Vertex AI generative models middleware.
public enum Gemini {

    public protocol Model {
        func generateContent(_ request: [String: Any]) throws -> Response
        var modelName: String { get }
    }

    public struct UsageMetadata: Sendable, Equatable {
        public let promptTokenCount: Int64
        public let candidatesTokenCount: Int64
        public let totalTokenCount: Int64
        public init(
            promptTokenCount: Int64 = 0,
            candidatesTokenCount: Int64 = 0,
            totalTokenCount: Int64 = 0
        ) {
            self.promptTokenCount = promptTokenCount
            self.candidatesTokenCount = candidatesTokenCount
            self.totalTokenCount = totalTokenCount
        }
    }

    public struct Part: Sendable, Equatable {
        public let hasFunctionCall: Bool
        public init(hasFunctionCall: Bool = false) {
            self.hasFunctionCall = hasFunctionCall
        }
    }

    public struct Candidate: Sendable {
        public let parts: [Part]
        public init(parts: [Part] = []) { self.parts = parts }
    }

    public struct Response: Sendable {
        public let usageMetadata: UsageMetadata
        public let candidates: [Candidate]
        public init(usageMetadata: UsageMetadata, candidates: [Candidate]) {
            self.usageMetadata = usageMetadata
            self.candidates = candidates
        }
    }

    public struct Options: Sendable {
        public var raiseOnEscalation: Bool
        public init(raiseOnEscalation: Bool = false) {
            self.raiseOnEscalation = raiseOnEscalation
        }
        public static let defaults = Options()
    }

    public final class BoundedModel {
        private let raw: Model
        private let execution: BoundedExecution
        private let opts: Options

        public init(raw: Model, execution: BoundedExecution, options: Options = .defaults) {
            self.raw = raw
            self.execution = execution
            self.opts = options
        }

        public func generateContent(_ request: [String: Any]) throws -> Response {
            let pre = execution.check()
            if pre == .locked { throw MiddlewareError.locked }
            if pre == .escalated, opts.raiseOnEscalation {
                throw MiddlewareError.escalationRaised
            }
            let resp: Response
            do {
                resp = try raw.generateContent(request)
            } catch {
                throw MiddlewareError.provider(
                    error.localizedDescription, underlying: error)
            }
            var tokens = resp.usageMetadata.totalTokenCount
            if tokens == 0 {
                tokens = resp.usageMetadata.promptTokenCount
                    + resp.usageMetadata.candidatesTokenCount
            }
            var toolCalls: Int64 = 0
            for c in resp.candidates {
                for p in c.parts {
                    if p.hasFunctionCall { toolCalls += 1 }
                }
            }
            let model = raw.modelName.isEmpty ? "unknown" : raw.modelName
            execution.recordStep(StepInput(
                tokens: tokens,
                toolCalls: toolCalls,
                tag: "gemini.generateContent:\(model)"))
            return resp
        }
    }
}
