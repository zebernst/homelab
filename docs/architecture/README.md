# Cluster Platform Architecture

Generated from Flux `Kustomization.spec.dependsOn` and declared Kustomize components.
Deploy edges define reconcile ordering; operational edges are optional and separate.

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

## Declarative monitoring (Gatus component)

These workloads expose synthetic checks via the shared Gatus component.
Monitoring depends on the target, not the other way around.

- `downloads/qbittorrent`
- `media/plex`
- `media/seerr`
- `media/wizarr`
- `observability/gatus`
- `observability/kromgo`
- `self-hosted/atuin`
- `self-hosted/rxresume`

## Artifacts

- `architecture/platform-deploy.json` — collapsed deploy graph for Stacktower
- `architecture/platform-operational.json` — monitor/backup/scale edges only
- `architecture/full-deploy.json` — all Kustomizations and deploy edges

```bash
stacktower render docs/architecture/platform-deploy.json -o docs/architecture/platform-deploy.svg
stacktower stats docs/architecture/platform-deploy.json
```
