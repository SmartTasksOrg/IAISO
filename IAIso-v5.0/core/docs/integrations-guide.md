# Writing IAIso Integrations

This guide is for people building plugins that connect IAIso to other
systems — SIEMs, identity providers, ERP systems, observability tools.
It exists specifically to avoid the pattern of shipping stub files
labeled "production integration" that do not actually integrate with
anything.

## The test for "real integration"

Before writing code, ask:

1. **Do I have access to the real system being integrated?** An instance,
   sandbox, or dev tenant. Not just docs.
2. **Can I demonstrate the integration working end-to-end?** Event
   actually reaches the destination, operator can query it, schema is
   what we said it would be.
3. **Am I prepared to maintain this?** APIs change. Integrations without
   a maintainer become bit-rotten stubs within 12-18 months.

If the answer to any of these is "no," don't publish the integration
under an IAIso namespace. It's fine to keep a work-in-progress branch
or a fork; it's not fine to mark something "production-ready" that
doesn't meet the test.

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
  what the integration does **and does not** do.
- It says "experimental" or "alpha" until someone has run it in
  production for at least 90 days.

## What NOT to do

- Don't publish an integration whose README contains "92% of Fortune 500
  use $PLATFORM, therefore IAIso powers 92% of Fortune 500." The market
  share of the platform you integrate with is not IAIso's market share.
- Don't publish 30 stub integrations to claim breadth. Five working
  integrations are worth more than fifty stubs that import the target
  SDK and do nothing useful.
- Don't make compliance claims on behalf of the integration. "This
  integration forwards audit events to Splunk" is a true, useful
  statement. "This integration makes your system SOC 2 compliant" is
  not — SOC 2 compliance is a property of an organization and its
  controls, not of any single technical integration.
