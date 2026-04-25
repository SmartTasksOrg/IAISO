Add a Go port as core/iaiso-go/ — operational simplicity, healthy LLM-SDK ecosystem.
Add a Rust port as core/iaiso-rust/ — performance-sensitive deployments.
gRPC coordinator sidecar — proto drafted in core/spec/coordinator/wire.proto; would let any future port participate in fleet coordination via a thin client instead of reimplementing the full Redis protocol.
Solution-pack runtime loader — graduate the JSON pack catalog from vision/components/sol/ into a feature both Python and Node SDKs consume.