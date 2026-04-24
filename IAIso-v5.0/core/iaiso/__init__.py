"""IAIso — experimental framework for bounded agent execution.

Public API:

    from iaiso import (
        BoundedExecution,
        PressureConfig,
        ConsentIssuer,
        ConsentVerifier,
        StdoutSink,
        JsonlFileSink,
    )

See `docs/getting-started.md` for an introduction and `docs/spec/` for the
stable interface specifications (event schema, consent token format).
"""

__version__ = "0.2.0"

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
    BoundedExecution,
    ExecutionLocked,
    Lifecycle,
    PressureConfig,
    PressureEngine,
    PressureSnapshot,
    ScopeRequired,
    StepInput,
    StepOutcome,
)

__all__ = [
    # Core
    "BoundedExecution",
    "ExecutionLocked",
    "Lifecycle",
    "PressureConfig",
    "PressureEngine",
    "PressureSnapshot",
    "ScopeRequired",
    "StepInput",
    "StepOutcome",
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
