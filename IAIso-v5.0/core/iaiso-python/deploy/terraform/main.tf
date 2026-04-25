###############################################################################
# IAIso Terraform module.
#
# Wraps the Helm chart at ../helm and provisions supporting cloud resources
# (optional: ElastiCache Redis, Secrets Manager entries for OIDC/SIEM).
#
# This module is intentionally modest — it only wires up the bits that are
# the same across deployments. Anything environment-specific (VPCs, IAM
# roles, network policies) should live in the calling Terraform, not here.
###############################################################################

terraform {
  required_version = ">= 1.5"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = ">= 2.13"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = ">= 2.27"
    }
  }
}

variable "release_name" {
  description = "Helm release name for the IAIso deployment."
  type        = string
  default     = "iaiso"
}

variable "namespace" {
  description = "Kubernetes namespace to deploy into."
  type        = string
  default     = "iaiso"
}

variable "chart_version" {
  description = "IAIso chart version. Must match a version published in your chart repo or a local path."
  type        = string
  default     = "0.1.0"
}

variable "chart_repository" {
  description = "OCI or HTTPS chart repository URL. Use null to use the local chart at ../helm."
  type        = string
  default     = null
}

variable "replica_count" {
  description = "Number of coordinator replicas."
  type        = number
  default     = 3
}

variable "image_repository" {
  description = "Container image repository for IAIso."
  type        = string
  default     = "iaiso"
}

variable "image_tag" {
  description = "Container image tag."
  type        = string
  default     = "0.1.0"
}

variable "redis_url" {
  description = "Redis connection URL reachable from the namespace."
  type        = string
}

variable "oidc_discovery_url" {
  description = "OIDC provider discovery URL (Okta, Auth0, Azure AD). Leave empty to disable."
  type        = string
  default     = ""
}

variable "oidc_audience" {
  description = "Expected OIDC token audience."
  type        = string
  default     = ""
}

variable "metrics_service_monitor_enabled" {
  description = "Create a Prometheus Operator ServiceMonitor."
  type        = bool
  default     = false
}

variable "policy_yaml" {
  description = "Inline policy YAML content. Takes precedence over chart defaults."
  type        = string
  default     = ""
}

resource "kubernetes_namespace" "iaiso" {
  metadata {
    name = var.namespace
    labels = {
      "pod-security.kubernetes.io/enforce" = "restricted"
      "pod-security.kubernetes.io/audit"   = "restricted"
      "pod-security.kubernetes.io/warn"    = "restricted"
    }
  }
}

resource "helm_release" "iaiso" {
  name       = var.release_name
  namespace  = kubernetes_namespace.iaiso.metadata[0].name
  repository = var.chart_repository
  chart      = var.chart_repository == null ? "${path.module}/../helm" : "iaiso"
  version    = var.chart_version

  values = [yamlencode({
    replicaCount = var.replica_count
    image = {
      repository = var.image_repository
      tag        = var.image_tag
    }
    redis = {
      url = var.redis_url
    }
    oidc = {
      discoveryUrl = var.oidc_discovery_url
      audience     = var.oidc_audience
    }
    metrics = {
      serviceMonitor = {
        enabled = var.metrics_service_monitor_enabled
      }
    }
    policy = {
      contents = var.policy_yaml
    }
  })]

  # Helm timeouts — default 5 min is tight for clusters with slow pulls.
  timeout = 600
}

output "release_namespace" {
  value = kubernetes_namespace.iaiso.metadata[0].name
}

output "release_name" {
  value = helm_release.iaiso.name
}
