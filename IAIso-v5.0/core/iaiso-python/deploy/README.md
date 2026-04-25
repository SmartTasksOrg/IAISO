# Deployment Templates

This directory contains template deployment artifacts for IAIso. They
are starting points — every production deployment needs environment-
specific customization (IAM, VPCs, service meshes, etc.) that is
deliberately out of scope here.

## Verification Required Before Production

These templates have **not been tested against real Kubernetes
clusters**. They follow current conventions and pass `helm lint` /
`terraform validate`, but the honest stance is: read them, adapt them,
run `helm template` / `terraform plan` yourself, and confirm they
match your organization's standards.

## Directory layout

```
deploy/
├── docker/          Dockerfile + docker-compose for local dev
├── helm/            Helm chart for Kubernetes deployment
└── terraform/       Terraform wrapper around the Helm chart
```

## Docker

Build the image:

```bash
docker build -t iaiso:0.1.0 -f deploy/docker/Dockerfile .
```

Run the CLI:

```bash
docker run --rm iaiso:0.1.0 --help
```

Local dev stack with Redis and Prometheus:

```bash
cd deploy/docker
docker-compose up
```

## Helm

Deploy the chart:

```bash
helm install iaiso ./deploy/helm \
  --namespace iaiso --create-namespace \
  --set redis.url=redis://redis-master:6379/0 \
  --set image.tag=0.1.0
```

Key values to override (`helm show values ./deploy/helm` for the full list):

- `replicaCount` — number of coordinator pods
- `redis.url` / `redis.passwordSecretRef` — Redis wiring
- `oidc.discoveryUrl` + `oidc.audience` — OIDC verification
- `policy.contents` — inline policy YAML
- `metrics.serviceMonitor.enabled` — create Prometheus Operator ServiceMonitor

The chart enforces restricted pod security (runAsNonRoot,
readOnlyRootFilesystem, no privilege escalation, all capabilities
dropped). If this doesn't match your cluster's security posture,
adjust `podSecurityContext` / `containerSecurityContext`.

## Terraform

The Terraform module at `deploy/terraform/` is a thin wrapper around
the Helm chart — it creates the namespace and applies the release with
the values you care about as Terraform variables. Use it if you manage
your cluster state with Terraform.

```bash
cd deploy/terraform/example
terraform init
terraform apply -var redis_url=redis://redis-master.redis.svc:6379/0
```

## What these templates deliberately do NOT do

1. Provision Redis. Use your own Redis service (ElastiCache, Memorystore,
   bitnami/redis Helm chart, etc.). We expect a URL, not a Redis cluster.
2. Provision an OIDC provider. Bring your own Okta / Auth0 / Entra.
3. Set up SIEM ingestion. IAIso ships sinks for several SIEMs; wire them
   up in your own application code, not in the infrastructure layer.
4. Configure ingress. The coordinator exposes only metrics; it's not a
   user-facing service. If you need external access, add your own
   Ingress / Gateway / VirtualService.

## If you're running a single process

You don't need any of this. `pip install iaiso` and use the library
directly. These templates matter when you need fleet-level coordination
or centralized metrics / audit / consent issuance.
