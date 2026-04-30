---
name: iaiso-deploy-docker
description: "Use this skill when packaging an IAIso-governed agent into a container. Triggers on Dockerfile, base image choice, non-root user, health probes. Do not use it for plain Python development — local pip is enough."
version: 1.0.0
tier: P1
category: deploy
framework: IAIso v5.0
license: See ../LICENSE
---

# Packaging IAIso in a container

## When this applies

A new agent service is being containerised, or an existing
one is adopting IAIso.

## Steps To Complete

1. **Pick a small base image.** `python:3.11-slim` is fine;
   distroless is smaller. Avoid full Debian unless your
   agent really needs it.

2. **Run as non-root.** Create a dedicated user and group
   (`useradd --uid 10001 iaiso`); chown the working
   directory; `USER iaiso` before `CMD`.

3. **Install the SDK at a pinned version.** Pinning is what
   makes the conformance suite a meaningful CI gate; an
   unpinned `iaiso` will silently move on tomorrow's
   release.

   ```dockerfile
   RUN pip install --no-cache-dir iaiso==0.2.0
   ```

4. **Mount the policy file, do not bake it in.** The image
   is environment-agnostic; the policy file changes per
   env. Mount via Kubernetes ConfigMap (see
   `iaiso-deploy-helm-chart`) or a Docker volume.

5. **Add a health probe.** A liveness probe that hits the
   admin CLI's `--help` or a tiny HTTP endpoint
   distinguishes "container alive" from "agent stuck in a
   lock". The `/healthz` reference endpoint reports `200
   OK` while non-LOCKED.

6. **Forward audit volume from container.** If using JSONL
   sink, mount `/var/log/iaiso` to a durable volume — the
   in-container ephemeral filesystem will not survive a
   restart.

## What this skill does NOT cover

- Helm-specific orchestration — see
  `../iaiso-deploy-helm-chart/SKILL.md`.
- Terraform infra around the container — see
  `../iaiso-deploy-terraform/SKILL.md`.

## References

- `core/iaiso-python/deploy/Dockerfile`
