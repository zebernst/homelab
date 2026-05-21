# Cluster Platform Architecture

Generated from Flux `Kustomization.spec.dependsOn`, declared Kustomize components,
and Helm/manifest monitoring configuration (ServiceMonitor, PodMonitor, VMServiceScrape).
Deploy edges define reconcile ordering; operational edges are separate edge kinds.

![Platform deploy tiers — app domains resting on shared platforms](platform-deploy.svg)

Regenerate the diagram with `task architecture:diagram` (requires [Stacktower](https://github.com/stacktower-io/stacktower)).

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

- `platform-deploy.svg` — collapsed deploy-tier diagram (committed)
- `platform-deploy.json`, `platform-operational.json`, `full-deploy.json` — generated locally by `task architecture:graph` (gitignored)

```bash
task architecture:diagram
stacktower stats docs/architecture/platform-deploy.json
```
