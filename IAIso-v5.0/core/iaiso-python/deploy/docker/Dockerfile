# syntax=docker/dockerfile:1.6
#
# IAIso production image.
#
# Ships the library, the admin CLI, and all optional extras that are
# safe to include (metrics, policy, OIDC, redis, bedrock, etc.). No
# provider SDKs with giant transitive deps (TF, CUDA bits) — those
# should live in your agent image, not the coordinator image.

FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY iaiso/ ./iaiso/

RUN pip install --no-cache-dir --upgrade pip build \
 && python -m build --wheel --outdir /wheels

# ----- runtime image -----

FROM python:3.12-slim

# Non-root user for the runtime. UID matches common Kubernetes
# security-context defaults (SecurityContext.runAsUser=65532).
RUN groupadd --gid 65532 iaiso \
 && useradd --uid 65532 --gid iaiso --home-dir /home/iaiso --create-home iaiso

COPY --from=builder /wheels/*.whl /tmp/

RUN pip install --no-cache-dir /tmp/iaiso-*.whl \
    "prometheus_client>=0.19" \
    "opentelemetry-api>=1.20" \
    "opentelemetry-sdk>=1.20" \
    "opentelemetry-exporter-otlp>=1.20" \
    "pyyaml>=6.0" \
    "redis>=5.0" \
    "pyjwt[crypto]>=2.8" \
 && rm /tmp/iaiso-*.whl

USER iaiso
WORKDIR /home/iaiso

# Default: run the CLI. Override CMD/ENTRYPOINT for specific services
# (e.g., a coordinator pod that launches a Redis-backed coordinator).
ENTRYPOINT ["python", "-m", "iaiso"]
CMD ["--help"]

# Healthcheck: policy template generation succeeds → basic install is
# intact. Override for service-specific liveness.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "from iaiso.policy import dump_policy_template; import tempfile, os; f = tempfile.mktemp(suffix='.yaml'); dump_policy_template(f); os.unlink(f)" || exit 1
