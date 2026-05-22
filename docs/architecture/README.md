# Cluster Platform Architecture

Generated from Flux `Kustomization.spec.dependsOn`. Customize vertical tiers, groups,
and partitions in [`tier-categories.yaml`](tier-categories.yaml).

| Vertical tier | Groups | Role |
| --- | --- | --- |
| Substrate | Substrate | CNI, DNS, PVC/CSI, snapshots — pods cannot run without this |
| Infrastructure | Platform · Observability | Infra providers vs metrics/logs/checks |
| Shared services | Data · AI | Shared Postgres/Redis and inference |
| Workloads | Workloads | User-facing applications |

```mermaid
flowchart BT

  %% Cross-tier dependsOn summary (higher tier -.-> lower tier it depends on)

  subgraph vt0["Substrate — Cluster-critical — pods cannot run without this (CNI, DNS, PVC/CSI, snapshots)"]
    subgraph g_substrate["Substrate — CNI, DNS, PVC provisioners, CSI, snapshots, device plugins, node labels"]
      subgraph p_substrate_substrate_cluster["cluster"]
        cilium["cilium"]
        class cilium substrate
      end
      subgraph p_substrate_substrate_gitops["gitops"]
        cluster_meta["cluster-meta"]
        class cluster_meta substrate
      end
      subgraph p_substrate_substrate_storage["storage"]
        nfs_subdir_external_provisioner["nfs-subdir-external-provisioner"]
        class nfs_subdir_external_provisioner substrate
        rook_ceph["rook-ceph"]
        class rook_ceph substrate
        rook_ceph_cluster["rook-ceph-cluster<br/>(42 deps)"]
        class rook_ceph_cluster substrate
        snapshot_controller["snapshot-controller"]
        class snapshot_controller substrate
        synology_csi_driver["synology-csi-driver"]
        class synology_csi_driver substrate
        volsync["volsync<br/>(30 deps)"]
        class volsync substrate
      end
    end
    hub_vt0(( ))
    class hub_vt0 hub
  end

  subgraph vt1["Infrastructure — Platform providers and observability at the same tier, distinct groups"]
    subgraph g_platform["Platform — Secrets, networking, auth, security, gitops"]
      subgraph p_platform_platform_auth["auth"]
        pocket_id["pocket-id"]
        class pocket_id platform
      end
      subgraph p_platform_platform_data_operators["data operators"]
        cloudnative_pg["cloudnative-pg"]
        class cloudnative_pg platform
      end
      subgraph p_platform_platform_gitops["gitops"]
        cluster_apps["cluster-apps"]
        class cluster_apps platform
        flux_operator["flux-operator"]
        class flux_operator platform
      end
      subgraph p_platform_platform_networking["networking"]
        ingress_nginx_external["ingress-nginx-external"]
        class ingress_nginx_external platform
        ingress_nginx_internal["ingress-nginx-internal"]
        class ingress_nginx_internal platform
      end
      subgraph p_platform_platform_secrets["secrets"]
        cluster_secrets["cluster-secrets"]
        class cluster_secrets platform
        external_secrets["external-secrets"]
        class external_secrets platform
        onepassword["onepassword<br/>(53 deps)"]
        class onepassword platform
      end
      subgraph p_platform_platform_security["security"]
        cert_manager["cert-manager"]
        class cert_manager platform
        cert_manager_issuers["cert-manager-issuers"]
        class cert_manager_issuers platform
      end
    end
    subgraph g_observability["Observability — Metrics, logs, alerting, synthetic checks — not an infra provider"]
      subgraph p_observability_observability_metrics["metrics"]
        victoria_metrics["victoria-metrics"]
        class victoria_metrics observability
        victoria_metrics_operator["victoria-metrics-operator<br/>(5 deps)"]
        class victoria_metrics_operator observability
      end
    end
    hub_vt1(( ))
    class hub_vt1 hub
  end

  subgraph vt2["Shared services — Data and AI at the same tier, distinct groups"]
    subgraph g_data["Data — Shared databases and cache clusters"]
      subgraph p_data_data_cache["cache"]
        dragonfly_cluster["dragonfly-cluster"]
        class dragonfly_cluster data
      end
      subgraph p_data_data_postgres["postgres"]
        cloudnative_pg_cluster["cloudnative-pg-cluster<br/>(20 deps)"]
        class cloudnative_pg_cluster data
      end
    end
    subgraph g_ai["AI — Shared inference infrastructure"]
      subgraph p_ai_ai_inference["inference"]
        ollama["ollama"]
        class ollama ai
      end
    end
    hub_vt2(( ))
    class hub_vt2 hub
  end

  subgraph vt3["Workloads — User-facing applications"]
    subgraph g_workloads["Workloads"]
      wl_ai["AI<br/>(4 ks)"]
      class wl_ai workloads
      wl_downloads["Downloads<br/>(20 ks)"]
      class wl_downloads workloads
      wl_fission["Fission<br/>(3 ks)"]
      class wl_fission workloads
      wl_games["Games<br/>(5 ks)"]
      class wl_games workloads
      wl_kube_system["Kube System<br/>(8 ks)"]
      class wl_kube_system workloads
      wl_media["Media<br/>(11 ks)"]
      class wl_media workloads
      wl_self_hosted["Self-Hosted<br/>(13 ks)"]
      class wl_self_hosted workloads
      wl_system_upgrade["System Upgrade<br/>(2 ks)"]
      class wl_system_upgrade workloads
    end
    hub_vt3(( ))
    class hub_vt3 hub
  end

  hub_vt1 -.-> hub_vt0
  hub_vt2 -.-> hub_vt0
  hub_vt2 -.-> hub_vt1
  hub_vt3 -.-> hub_vt0
  hub_vt3 -.-> hub_vt1
  hub_vt3 -.-> hub_vt2

  %% styling
  classDef hub fill:none,stroke:none,color:transparent
  classDef substrate fill:#1f2937,stroke:#9ca3af,color:#f9fafb
  classDef platform fill:#1e3a5f,stroke:#60a5fa,color:#eff6ff
  classDef observability fill:#312e81,stroke:#a78bfa,color:#f5f3ff
  classDef data fill:#14532d,stroke:#4ade80,color:#f0fdf4
  classDef ai fill:#581c87,stroke:#d8b4fe,color:#faf5ff
  classDef workloads fill:#422006,stroke:#fbbf24,color:#fffbeb
```

Regenerate: `task architecture:graph`

Dashed edges summarize cross-tier Flux `dependsOn` (higher tier depends on lower).
Individual Kustomization edges are omitted to keep the diagram readable.

## Load-bearing platforms

Kustomizations with the most direct `dependsOn` inbound edges.

| Kustomization | Dependents | Group | dependsOn depth |
| --- | ---: | --- | ---: |
| `external-secrets/onepassword` | 53 | Platform | 1 |
| `rook-ceph/rook-ceph-cluster` | 42 | Substrate | 2 |
| `volsync-system/volsync` | 30 | Substrate | 0 |
| `database/cloudnative-pg-cluster` | 20 | Data | 3 |
| `observability/victoria-metrics-operator` | 5 | Observability | 0 |
| `ai/ollama` | 3 | AI | 3 |
| `cert-manager/cert-manager` | 3 | Platform | 0 |
| `cert-manager/cert-manager-issuers` | 3 | Platform | 1 |
| `downloads/qbittorrent` | 3 | Workloads | 3 |
| `games/bluemap` | 3 | Workloads | 3 |
| `observability/victoria-metrics` | 2 | Observability | 3 |
| `cert-manager/step-issuer` | 2 | Platform | 1 |
| `database/cloudnative-pg` | 2 | Platform | 2 |
| `kube-system/cilium` | 2 | Substrate | 0 |
| `kube-system/snapshot-controller` | 2 | Substrate | 0 |

## Kustomizations by group

### Substrate

**Substrate**

- `flux-system/cluster-meta` (1 deps)
- `kube-system/cilium` (2 deps)
- `kube-system/coredns`
- `kube-system/generic-device-plugin`
- `kube-system/intel-device-plugin`
- `kube-system/intel-device-plugin-gpu`
- `kube-system/kubelet-csr-approver`
- `kube-system/nfs-subdir-external-provisioner`
- `kube-system/node-feature-discovery` (1 deps)
- `kube-system/node-feature-discovery-features`
- `kube-system/nvidia-device-plugin`
- `kube-system/priority-class`
- `kube-system/snapshot-controller` (2 deps)
- `kube-system/spegel`
- `kube-system/synology-csi-driver`
- `openebs-system/openebs` (1 deps)
- `rook-ceph/rook-ceph` (1 deps)
- `rook-ceph/rook-ceph-cluster` (42 deps)
- `volsync-system/volsync` (30 deps)

### Infrastructure

**Platform**

- `auth/pocket-id` (1 deps)
- `auth/tinyauth`
- `cert-manager/cert-manager` (3 deps)
- `cert-manager/cert-manager-issuers` (3 deps)
- `cert-manager/cert-manager-tls` (2 deps)
- `cert-manager/step-issuer` (2 deps)
- `cert-manager/step-issuer-issuers` (1 deps)
- `cert-manager/step-issuer-tls`
- `database/cloudnative-pg` (2 deps)
- `database/dragonfly` (1 deps)
- `external-secrets/cluster-secrets` (1 deps)
- `external-secrets/external-secrets` (1 deps)
- `external-secrets/onepassword` (53 deps)
- `flux-system/cluster-apps`
- `flux-system/flux-instance`
- `flux-system/flux-operator` (1 deps)
- `kube-system/cilium-config` (1 deps)
- `kube-system/cilium-gateway`
- `network/cloudflared`
- `network/echo-server`
- `network/external-dns-cloudflare`
- `network/external-dns-unifi`
- `network/ingress-nginx-external`
- `network/ingress-nginx-internal`
- `network/smtp-relay` (1 deps)
- `network/tailscale-operator`

**Observability**

- `observability/blackbox-exporter` (1 deps)
- `observability/blackbox-exporter-probes`
- `observability/fluent-bit`
- `observability/gatus`
- `observability/grafana`
- `observability/karma`
- `observability/keda`
- `observability/kromgo`
- `observability/silence-operator` (1 deps)
- `observability/silence-operator-silences`
- `observability/smartctl-exporter`
- `observability/snmp-exporter`
- `observability/unpoller`
- `observability/victoria-logs` (2 deps)
- `observability/victoria-metrics` (2 deps)
- `observability/victoria-metrics-operator` (5 deps)
- `observability/vmalert`

### Shared services

**Data**

- `database/cloudnative-pg-cluster` (20 deps)
- `database/dragonfly-cluster` (2 deps)
- `database/mariadb` (1 deps)

**AI**

- `ai/ollama` (3 deps)

### Workloads

**Workloads**

- AI: 4
- Downloads: 20
- Fission: 3
- Games: 5
- Kube System: 8
- Media: 11
- Self-Hosted: 13
- System Upgrade: 2

## Artifacts

- [`platform-tiers.mmd`](platform-tiers.mmd) — Mermaid source (also embedded above)
- [`tier-categories.yaml`](tier-categories.yaml) — vertical tiers, groups, partitions
