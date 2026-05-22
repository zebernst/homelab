# Cluster Platform Architecture

Generated from Flux `Kustomization.spec.dependsOn`, declared Kustomize components,
and Helm/manifest monitoring configuration (ServiceMonitor, PodMonitor, VMServiceScrape).
Deploy edges define reconcile ordering; operational edges are separate edge kinds.

## Platform tier model

Conceptual deploy tiers and platform categories, generated from Flux `dependsOn`.
Workloads at tier 4+ collapse into per-namespace groups. Customize labels and grouping
in [`tier-categories.yaml`](tier-categories.yaml).

```mermaid
flowchart BT

  subgraph tier_0["Tier 0 — Cluster substrate"]
    subgraph t0_platform_cluster["platform/cluster"]
      snapshot_controller["snapshot-controller"]
    end
    subgraph t0_platform_gitops["platform/gitops"]
      cluster_meta["cluster-meta"]
    end
    subgraph t0_platform_networking["platform/networking"]
      cilium["cilium"]
    end
    subgraph t0_platform_observability["platform/observability"]
      victoria_metrics_operator["victoria-metrics-operator"]
    end
    subgraph t0_platform_secrets["platform/secrets"]
      external_secrets["external-secrets"]
    end
    subgraph t0_platform_security["platform/security"]
      cert_manager["cert-manager"]
    end
    subgraph t0_platform_storage["platform/storage"]
      volsync["volsync"]
    end
  end

  subgraph tier_1["Tier 1 — Platform services"]
    subgraph t1_platform_gitops["platform/gitops"]
      cluster_apps["cluster-apps"]
    end
    subgraph t1_platform_secrets["platform/secrets"]
      onepassword["onepassword"]
    end
    subgraph t1_platform_security["platform/security"]
      cert_manager_issuers["cert-manager-issuers"]
    end
    subgraph t1_platform_storage["platform/storage"]
      rook_ceph["rook-ceph"]
    end
  end

  subgraph tier_2["Tier 2 — Shared infrastructure"]
    subgraph t2_platform_data["platform/data"]
      cloudnative_pg["cloudnative-pg"]
    end
    subgraph t2_platform_secrets["platform/secrets"]
      cluster_secrets["cluster-secrets"]
    end
    subgraph t2_platform_storage["platform/storage"]
      rook_ceph_cluster["rook-ceph-cluster"]
    end
  end

  subgraph tier_3["Tier 3 — Data and edge platforms"]
    subgraph t3_platform_data["platform/data"]
      cloudnative_pg_cluster["cloudnative-pg-cluster"]
    end
    subgraph t3_platform_networking["platform/networking"]
      ingress_nginx_external["ingress-nginx-external"]
      ingress_nginx_internal["ingress-nginx-internal"]
    end
    subgraph t3_platform_observability["platform/observability"]
      victoria_logs["victoria-logs"]
      victoria_metrics["victoria-metrics"]
    end
    subgraph t3_workloads["workloads"]
      bluemap["bluemap"]
      ollama["ollama"]
      qbittorrent["qbittorrent"]
    end
  end

  subgraph tier_4["Tier 4 — Workloads"]
    subgraph t4_workloads["workloads"]
      workloads_ai["AI<br/>(4 ks)"]
      workloads_auth["Auth<br/>(2 ks)"]
      workloads_downloads["Downloads<br/>(11 ks)"]
      workloads_fission["Fission<br/>(1 ks)"]
      workloads_games["Games<br/>(3 ks)"]
      workloads_media["Media<br/>(2 ks)"]
      workloads_observability["Observability<br/>(3 ks)"]
      workloads_self_hosted["Self-Hosted<br/>(9 ks)"]
    end
  end

  bluemap --> rook_ceph_cluster
  cert_manager_issuers --> cert_manager
  cloudnative_pg --> onepassword
  cloudnative_pg_cluster --> cloudnative_pg
  cluster_apps --> cluster_meta
  cluster_secrets --> onepassword
  ollama --> rook_ceph_cluster
  onepassword --> external_secrets
  qbittorrent --> onepassword
  qbittorrent --> rook_ceph_cluster
  qbittorrent --> volsync
  rook_ceph --> snapshot_controller
  rook_ceph_cluster --> rook_ceph
  victoria_logs --> rook_ceph_cluster
  victoria_metrics --> onepassword
  victoria_metrics --> rook_ceph_cluster
  victoria_metrics --> victoria_metrics_operator
  workloads_ai --> ollama
  workloads_ai --> onepassword
  workloads_ai --> rook_ceph_cluster
  workloads_ai --> victoria_metrics
  workloads_ai --> volsync
  workloads_auth --> cloudnative_pg_cluster
  workloads_auth --> onepassword
  workloads_auth --> rook_ceph_cluster
  workloads_auth --> volsync
  workloads_downloads --> cloudnative_pg_cluster
  workloads_downloads --> onepassword
  workloads_downloads --> qbittorrent
  workloads_downloads --> rook_ceph_cluster
  workloads_downloads --> volsync
  workloads_fission --> onepassword
  workloads_games --> bluemap
  workloads_games --> onepassword
  workloads_games --> rook_ceph_cluster
  workloads_games --> volsync
  workloads_media --> cloudnative_pg_cluster
  workloads_media --> onepassword
  workloads_media --> rook_ceph_cluster
  workloads_media --> volsync
  workloads_observability --> cloudnative_pg_cluster
  workloads_observability --> onepassword
  workloads_observability --> victoria_logs
  workloads_observability --> victoria_metrics
  workloads_observability --> victoria_metrics_operator
  workloads_self_hosted --> cloudnative_pg
  workloads_self_hosted --> cloudnative_pg_cluster
  workloads_self_hosted --> cluster_secrets
  workloads_self_hosted --> onepassword
  workloads_self_hosted --> rook_ceph_cluster
  workloads_self_hosted --> volsync
```

## Load-bearing view (Stacktower)

Stacktower emphasizes fan-out and load-bearing platforms; the Mermaid chart above
emphasizes named tiers and platform categories. Use both: Mermaid for architecture
storytelling, Stacktower for dependency density and DR prioritization stats.

![Platform deploy tiers — app domains resting on shared platforms](platform-deploy.svg)

Regenerate with `task architecture:diagram` (requires [Stacktower](https://github.com/stacktower-io/stacktower)).

## Load-bearing platforms

| Platform | Direct dependents | Tier |
| --- | ---: | ---: |
| `external-secrets/onepassword` | 53 | 1 |
| `rook-ceph/rook-ceph-cluster` | 42 | 2 |
| `volsync-system/volsync` | 30 | 0 |
| `database/cloudnative-pg-cluster` | 20 | 3 |
| `observability/victoria-metrics-operator` | 5 | 0 |
| `cert-manager/cert-manager` | 3 | 0 |
| `cert-manager/cert-manager-issuers` | 3 | 1 |
| `observability/victoria-metrics` | 2 | 3 |
| `database/cloudnative-pg` | 2 | 2 |
| `kube-system/cilium` | 2 | 0 |
| `kube-system/snapshot-controller` | 2 | 0 |
| `observability/victoria-logs` | 2 | 3 |
| `external-secrets/external-secrets` | 1 | 0 |
| `rook-ceph/rook-ceph` | 1 | 1 |
| `flux-system/cluster-meta` | 1 | 0 |

## Deploy tiers

Tier 0 sits at the bottom of the reconcile stack; higher tiers rest on lower ones.

### Tier 0

- `cert-manager/cert-manager` (3 dependents)
- `database/dragonfly` (1 dependents)
- `external-secrets/external-secrets` (1 dependents)
- `fission/fission-crds` (1 dependents)
- `flux-system/cluster-meta` (1 dependents)
- `flux-system/flux-operator` (1 dependents)
- `kube-system/cilium` (2 dependents)
- `kube-system/node-feature-discovery` (1 dependents)
- `kube-system/self-node-remediation` (1 dependents)
- `kube-system/snapshot-controller` (2 dependents)
- `observability/silence-operator` (1 dependents)
- `observability/victoria-metrics-operator` (5 dependents)
- `openebs-system/openebs` (1 dependents)
- `system-upgrade/tuppr` (1 dependents)
- `volsync-system/volsync` (30 dependents)

### Tier 1

- `cert-manager/cert-manager-issuers` (3 dependents)
- `cert-manager/step-issuer` (2 dependents)
- `database/dragonfly-cluster` (2 dependents)
- `external-secrets/onepassword` (53 dependents)
- `flux-system/cluster-apps`
- `kube-system/cilium-config` (1 dependents)
- `kube-system/node-healthcheck` (1 dependents)
- `observability/blackbox-exporter` (1 dependents)
- `rook-ceph/rook-ceph` (1 dependents)

### Tier 2

- `cert-manager/cert-manager-tls` (2 dependents)
- `cert-manager/step-issuer-issuers` (1 dependents)
- `database/cloudnative-pg` (2 dependents)
- `external-secrets/cluster-secrets` (1 dependents)
- `network/smtp-relay` (1 dependents)
- `rook-ceph/rook-ceph-cluster` (42 dependents)

### Tier 3

- `ai/ollama` (3 dependents)
- `database/cloudnative-pg-cluster` (20 dependents)
- `database/mariadb` (1 dependents)
- `downloads/qbittorrent` (3 dependents)
- `fission/fission` (1 dependents)
- `games/bluemap` (3 dependents)
- `observability/victoria-logs` (2 dependents)
- `observability/victoria-metrics` (2 dependents)
- `self-hosted/nominatim` (1 dependents)

### Tier 4

- `ai/holmesgpt` (1 dependents)
- `auth/pocket-id` (1 dependents)
- `downloads/sonarr` (1 dependents)

## Synthetic monitoring (Gatus component)

These workloads expose HTTP checks via the shared Gatus component.
Edge direction: `observability/gatus` → workload.

- `downloads/qbittorrent`
- `media/plex`
- `media/seerr`
- `media/wizarr`
- `observability/gatus`
- `observability/kromgo`
- `self-hosted/atuin`
- `self-hosted/rxresume`

## Metrics scraping (Prometheus / Victoria Metrics)

Detected from Helm chart values (`serviceMonitor`, `podMonitor`, `monitoring.enabled`)
and raw Victoria Metrics scrape CRs in Git. These are first-class cluster relationships
even when the chart renders the monitor object instead of a checked-in manifest.

Edge direction: `observability/victoria-metrics-operator` → workload.

- `ai/ollama` (VMProbe)
- `ai/open-webui` (VMProbe)
- `auth/pocket-id` (serviceMonitor)
- `auth/tinyauth` (VMProbe)
- `database/dragonfly` (serviceMonitor)
- `database/dragonfly-cluster` (VMPodScrape)
- `database/mariadb` (serviceMonitor)
- `downloads/autobrr` (serviceMonitor)
- `downloads/bazarr` (serviceMonitor)
- `downloads/bazarr-uhd` (serviceMonitor)
- `downloads/cross-seed` (VMProbe)
- `downloads/flaresolverr` (VMProbe)
- `downloads/lidarr` (serviceMonitor)
- `downloads/omegabrr` (VMProbe)
- `downloads/openbooks` (VMProbe)
- `downloads/prowlarr` (serviceMonitor)
- `downloads/qbittorrent` (VMProbe)
- `downloads/qui` (serviceMonitor)
- `downloads/radarr` (serviceMonitor)
- `downloads/radarr-uhd` (serviceMonitor)
- `downloads/seasonpackarr` (VMProbe)
- `downloads/sonarr` (serviceMonitor)
- `downloads/sonarr-uhd` (serviceMonitor)
- `downloads/unpackerr` (serviceMonitor)
- `downloads/whisparr` (VMProbe)
- `external-secrets/external-secrets` (serviceMonitor)
- `external-secrets/onepassword` (VMProbe)
- `fission/fission` (serviceMonitor)
- `flux-system/flux-operator` (serviceMonitor)
- `games/atm10` (serviceMonitor)
- `games/atmons` (serviceMonitor)
- `games/mc-router` (serviceMonitor)
- `games/vanilla` (serviceMonitor)
- `kube-system/cilium` (serviceMonitor)
- `kube-system/descheduler` (serviceMonitor)
- `kube-system/kubelet-csr-approver` (serviceMonitor)
- `kube-system/metrics-server` (serviceMonitor)
- `kube-system/node-feature-discovery` (serviceMonitor)
- `kube-system/node-problem-detector` (serviceMonitor)
- `kube-system/reloader` (podMonitor)
- `kube-system/snapshot-controller` (serviceMonitor)
- `kube-system/spegel` (serviceMonitor)
- `media/agregarr` (VMProbe)
- `media/booklore` (VMProbe)
- `media/capacitarr` (VMProbe)
- `media/maintainerr` (VMProbe)
- `media/shelfmark` (VMProbe)
- `media/stash` (VMProbe)
- `media/steam` (VMProbe)
- `media/tautulli` (VMProbe)
- `network/cloudflared` (serviceMonitor)
- `network/echo-server` (serviceMonitor)
- `network/external-dns-cloudflare` (serviceMonitor)
- `network/ingress-nginx-external` (serviceMonitor)
- `network/ingress-nginx-internal` (serviceMonitor)
- `network/smtp-relay` (serviceMonitor)
- `observability/blackbox-exporter` (serviceMonitor)
- `observability/blackbox-exporter-probes` (VMProbe)
- `observability/fluent-bit` (serviceMonitor)
- `observability/gatus` (serviceMonitor)
- `observability/grafana` (serviceMonitor)
- `observability/karma` (serviceMonitor)
- `observability/keda` (serviceMonitor)
- `observability/smartctl-exporter` (serviceMonitor)
- `observability/snmp-exporter` (serviceMonitor)
- `observability/unpoller` (serviceMonitor)
- `observability/victoria-logs` (serviceMonitor)
- `observability/victoria-metrics-operator` (serviceMonitor)
- `observability/vmalert` (serviceMonitor)
- `rook-ceph/rook-ceph` (monitoring, serviceMonitor)
- `rook-ceph/rook-ceph-cluster` (monitoring)
- `self-hosted/atuin` (serviceMonitor)
- `self-hosted/dawarich` (serviceMonitor)
- `self-hosted/glance` (VMProbe)
- `self-hosted/hajimari` (VMProbe)
- `self-hosted/homebox` (VMProbe)
- `self-hosted/it-tools` (VMProbe)
- `self-hosted/mealie` (VMProbe)
- `self-hosted/nocodb` (VMProbe)
- `self-hosted/nominatim` (VMProbe)
- `self-hosted/paperless` (serviceMonitor)
- `self-hosted/radicale` (VMProbe)
- `self-hosted/unwrapped` (VMProbe)
- `volsync-system/volsync` (VMServiceScrape)

## Operational edge summary

- `metrics`: 84
- `monitor`: 8
- `backup`: 32
- `scale`: 17

## Artifacts

- `platform-deploy.svg` — Stacktower load-bearing view (committed)
- `platform-tiers.mmd` — Mermaid tier model source (committed; also embedded above)
- `tier-categories.yaml` — tier labels and platform category rules
- `platform-deploy.json`, `platform-operational.json`, `full-deploy.json` — generated locally by `task architecture:graph` (gitignored)

```bash
task architecture:diagram
stacktower stats docs/architecture/platform-deploy.json
```
