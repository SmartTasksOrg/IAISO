# Example: deploy IAIso into an existing Kubernetes cluster.
#
# Adjust the kubernetes/helm providers for your environment, then run:
#   terraform init
#   terraform plan  -var redis_url=redis://redis-master.redis.svc:6379/0
#   terraform apply -var redis_url=redis://redis-master.redis.svc:6379/0

terraform {
  required_version = ">= 1.5"
}

provider "kubernetes" {
  config_path = "~/.kube/config"
}

provider "helm" {
  kubernetes {
    config_path = "~/.kube/config"
  }
}

variable "redis_url" {
  type = string
}

module "iaiso" {
  source = "../"   # or a published module source

  namespace        = "iaiso"
  replica_count    = 3
  redis_url        = var.redis_url

  # Optional OIDC integration
  oidc_discovery_url = "https://dev-12345.okta.com/oauth2/default/.well-known/openid-configuration"
  oidc_audience      = "api://my-agent"

  # Enable ServiceMonitor if you run Prometheus Operator
  metrics_service_monitor_enabled = true

  policy_yaml = <<-EOT
    version: "1"
    pressure:
      token_coefficient: 0.015
      escalation_threshold: 0.85
      release_threshold: 0.95
    coordinator:
      aggregator: sum
      escalation_threshold: 5.0
      release_threshold: 8.0
    consent:
      issuer: "my-org"
      default_ttl_seconds: 3600
  EOT
}
