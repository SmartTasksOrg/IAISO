---
name: iaiso-redteam-coordinator-poisoning
description: "Use this skill for authorised red-team probes targeting coordinator hash poisoning in IAIso deployments. Do not use it for unrelated threats — see `iaiso-redteam-router`."
version: 1.0.0
tier: P3
category: redteam
framework: IAIso v5.0
license: See ../LICENSE
---

# Red-team probe — coordinator hash poisoning

## When this applies

Authorised adversarial assessment specifically targeting
coordinator hash poisoning.

## Steps To Complete

1. **Confirm rules of engagement.** Authorised target,
   authorised window, abort criteria, on-call reachable.

2. **Set up the probe.**

   Technique: Connect a rogue client to the same Redis with the same prefix and id; HSET fictitious execution pressures to inflate aggregate; observe whether legitimate clients react to false fleet escalation.

3. **Run the probe in a non-prod environment first.** A
   successful probe in prod is a finding AND a production
   incident; do not combine the two. Stage first.

4. **Watch for the success signal.** Probe succeeds if `coordinator.escalation` fires from the false data and legitimate workers throttle / escalate in response.

   Capture the audit trail covering the probe.

5. **If the probe succeeds, the deployment has a finding.**
   The defence path is: Restrict Redis ACL to authorised clients only; consider HMAC on field values; or migrate to a coordinator with stronger authorship guarantees (gRPC sidecar when available).

6. **If the probe fails (the framework holds), document
   that as a positive control.** "We tested X; the framework
   prevented it" is itself audit-relevant evidence.

## What this skill does NOT cover

- Probes for other threats — see other `iaiso-redteam-*`.
- Defence implementation — see the relevant deployment skills.

## References

- `core/spec/pressure/README.md`
- `core/spec/consent/README.md`
