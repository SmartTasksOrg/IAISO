import Foundation

/// Appends events as JSONL to a file. I/O errors are silently dropped.
public final class JSONLFileSink: Sink, @unchecked Sendable {
    private let lock = NSLock()
    private let url: URL

    public init(path: String) {
        self.url = URL(fileURLWithPath: path)
    }

    public init(url: URL) {
        self.url = url
    }

    public func emit(_ event: Event) {
        let line = event.toJSON() + "\n"
        guard let bytes = line.data(using: .utf8) else { return }
        lock.lock()
        defer { lock.unlock() }
        do {
            if FileManager.default.fileExists(atPath: url.path) {
                let handle = try FileHandle(forWritingTo: url)
                defer { try? handle.close() }
                try handle.seekToEnd()
                try handle.write(contentsOf: bytes)
            } else {
                try bytes.write(to: url, options: .atomic)
            }
        } catch {
            // Silently drop — sinks must not propagate I/O errors.
        }
    }
}
