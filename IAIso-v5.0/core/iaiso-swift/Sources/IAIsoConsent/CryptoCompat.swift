// Cross-platform crypto imports: CryptoKit on Apple platforms,
// swift-crypto's `Crypto` module on Linux. Both provide the same API
// (`HMAC`, `SymmetricKey`, etc.) so consuming code can `import IAIsoConsent`
// and use the types transparently.
//
// On Linux, add the swift-crypto package dependency to the consuming
// `Package.swift`:
//
//     .package(url: "https://github.com/apple/swift-crypto.git", from: "3.0.0")
//
// and the IAIsoConsent target depends on `Crypto`. On Apple platforms,
// CryptoKit is built into the system frameworks — no dependency needed.

#if canImport(CryptoKit)
@_exported import CryptoKit
#elseif canImport(Crypto)
@_exported import Crypto
#endif
