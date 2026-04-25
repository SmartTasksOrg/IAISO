# Writing IAIso Integrations

This guide is for people building plugins that connect IAIso to other
systems — SIEMs, identity providers, ERP systems, observability tools.
It describes the standards an integration should meet before it ships
under an IAIso namespace, so that every integration in the registry
delivers a verified end-to-end connection with its target system.

## The bar for a registry-listed integration

Before writing code, ensure:

1. **Access to the target system.** An instance, sandbox, or dev tenant
   to test against — not just documentation.
2. **End-to-end demonstration.** The event actually reaches the
   destination, an operator can query it in the target system, and the
   schema matches what the integration's docs describe.
3. **A maintainer.** APIs evolve. A named maintainer keeps the
   integration current as the target's API changes over time.

Integrations under development are welcome as in-progress branches or
forks. Promotion into the registry happens when the three items above
are satisfied.

## Anatomy of a good integration

### Outbound (IAIso → external system)

Goal: ship audit events from IAIso to the external system in the format
that system expects.

Pattern: implement a `AuditSink`. Do not subclass `WebhookSink` unless
you need the threading and queuing; most SIEM clients provide their
own batching.

```python
from iaiso.audit import AuditEvent, AuditSink

class MySiemSink(AuditSink):
    def __init__(self, client, source: str):
        self._client = client  # the SIEM's own SDK client
        self._source = source

    def emit(self, event: AuditEvent) -> None:
        self._client.send({
            "source": self._source,
            "event_type": event.kind,
            "timestamp": event.timestamp,
            "attributes": event.data,
            # Map IAIso's "execution_id" to whatever the SIEM calls it
            "trace_id": event.execution_id,
        })
```

Essential checklist:

- [ ] The sink is thread-safe (the engine may emit from multiple threads).
- [ ] Failures in `emit()` do not raise (or are caught by the caller).
- [ ] There's a `close()` method (and `__enter__`/`__exit__`) that
  flushes pending events.
- [ ] Network calls have timeouts.
- [ ] Retries (if any) have a bounded budget.
- [ ] Events dropped due to backpressure are counted and exposed.

### Inbound (external system → IAIso)

Goal: let an external system (identity provider, policy engine) issue
ConsentScope tokens that IAIso verifies.

Pattern: implement an adapter that maps the external system's
authorization decisions to IAIso tokens. In most cases you will run
an `ConsentIssuer` on your side and configure the external system to
call it as part of its flow — not the other way around.

```python
# Example: an Okta webhook that, on successful SSO + MFA, calls
# your issuer service to mint a scoped token for a specific execution.

from iaiso import ConsentIssuer

def on_okta_session_established(okta_claims: dict, execution_id: str):
    scopes = map_okta_groups_to_iaiso_scopes(okta_claims["groups"])
    token = issuer.issue(
        subject=okta_claims["sub"],
        scopes=scopes,
        execution_id=execution_id,
        ttl_seconds=900,
        metadata={
            "okta_session": okta_claims["sid"],
            "mfa_at": okta_claims["auth_time"],
        },
    )
    return token.token
```

Essential checklist:

- [ ] The mapping from external authorization to IAIso scopes is
  documented and version-controlled. Don't let "what scopes get
  granted" be an implicit artifact of code buried in an adapter.
- [ ] MFA / step-up auth signals from the external system are captured
  in token metadata.
- [ ] Revocation signals from the external system (logout, session
  invalidation) propagate to the IAIso revocation list.
- [ ] The issuer service has its own audit log (in addition to IAIso's).
  Token issuance is a privileged operation and should be logged
  separately from token use.

## Publishing conventions

For an integration to be listed in the main IAIso documentation:

- It lives at `iaiso.integrations.<system>` (for plugins in this repo)
  or `iaiso-<system>` on PyPI (for third-party plugins).
- It has its own test suite that runs against either a real sandbox
  instance or a well-documented mock.
- Its README documents: supported versions of the external system,
  credentials/setup required, a working end-to-end example, and
  the integration's scope.
- Status is labeled clearly: **preview** during initial release,
  **stable** after 90+ days of reported production use.

## Integration quality standards

- **Accurate scope descriptions.** An integration's reach is measured
  by operators who have deployed it. Describe what the integration
  provides concretely — what events flow, what signals are captured,
  what the operator sees in the target system.
- **Depth over breadth.** One well-tested integration with a
  reproducible end-to-end example contributes more than multiple
  integrations that import the target SDK without exercising it.
- **Scope integration claims to the integration.** "This integration
  forwards audit events to Splunk in HEC format" is a concrete,
  verifiable statement. Certification claims (SOC 2, FedRAMP, HIPAA)
  attach to the operator's audited deployment rather than to any
  single technical integration, so they are framed as "IAIso's audit
  artifacts support SOC 2 evidence" in the integration's README.
