"""IAIso — reference SDK for the IAIso bounded-agent-execution framework.

Public API:

    from iaiso import (
        BoundedExecution,
        PressureConfig,
        ConsentIssuer,
        ConsentVerifier,
        StdoutSink,
        JsonlFileSink,
    )

See `docs/getting-started.md` for an introduction and `spec/` for the
normative interface specifications (pressure math, consent tokens,
audit events, policy format).
"""

__version__ = "0.3.0"

from iaiso.audit import (
    AuditEvent,
    AuditSink,
    FanoutSink,
    JsonlFileSink,
    MemorySink,
    NullSink,
    StdoutSink,
)
from iaiso.consent import (
    ConsentError,
    ConsentIssuer,
    ConsentScope,
    ConsentVerifier,
    ExpiredToken,
    InsufficientScope,
    InvalidToken,
    RevocationList,
    RevokedToken,
    generate_hs256_secret,
)
from iaiso.coordination import (
    CoordinatorConfig,
    CoordinatorSnapshot,
    MaxAggregator,
    MeanAggregator,
    SharedPressureCoordinator,
    SumAggregator,
    WeightedSumAggregator,
)
from iaiso.core import (
    ENFORCEMENT_PERMISSIVE,
    ENFORCEMENT_STRICT,
    BoundedExecution,
    ExecutionLocked,
    Lifecycle,
    PressureConfig,
    PressureEngine,
    PressureSnapshot,
    ScopeRequired,
    StepInput,
    StepOutcome,
    StrictModeError,
)

__all__ = [
    # Core
    "ENFORCEMENT_PERMISSIVE",
    "ENFORCEMENT_STRICT",
    "BoundedExecution",
    "ExecutionLocked",
    "Lifecycle",
    "PressureConfig",
    "PressureEngine",
    "PressureSnapshot",
    "ScopeRequired",
    "StepInput",
    "StepOutcome",
    "StrictModeError",
    # Consent
    "ConsentError",
    "ConsentIssuer",
    "ConsentScope",
    "ConsentVerifier",
    "ExpiredToken",
    "InsufficientScope",
    "InvalidToken",
    "RevocationList",
    "RevokedToken",
    "generate_hs256_secret",
    # Audit
    "AuditEvent",
    "AuditSink",
    "FanoutSink",
    "JsonlFileSink",
    "MemorySink",
    "NullSink",
    "StdoutSink",
    # Coordination
    "CoordinatorConfig",
    "CoordinatorSnapshot",
    "MaxAggregator",
    "MeanAggregator",
    "SharedPressureCoordinator",
    "SumAggregator",
    "WeightedSumAggregator",
    # Version
    "__version__",
]