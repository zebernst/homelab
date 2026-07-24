# Cilium Network Policies — Implementation Plan

This document captures the planning session for introducing CiliumNetworkPolicies to the homelab cluster. Pick this up in a future session by reading this file end-to-end first.

---

## Context

The cluster runs Cilium 1.19.1 in a near-comprehensive feature configuration (kube-proxy replacement, BGP control plane, L2 announcements, DSR + Maglev, Gateway API with Envoy L7, Hubble, BIG TCP, Bandwidth Manager with BBR). Despite this, **zero network policies exist**. Every pod can reach every other pod, every service, and the open internet without restriction.

This planning session was created to design a safe rollout of CiliumNetworkPolicies that introduces zero-trust networking without breaking the many cross-namespace flows present in the cluster.

### Sibling work that has already shipped on other branches

- `claude/cilium-feature-inventory-79YSq` — added Tetragon (eBPF runtime security observability) and enabled WireGuard node-to-node encryption (`encryption.enabled: true, type: wireguard, nodeEncryption: true`). WireGuard + DSR was verified compatible (issue cilium/cilium#28492 closed as fixed by PR #30240; only LB DSR return packet encryption is still an open feature request — not a connectivity blocker).
- `claude/cilium-spire-mtls` — enabled SPIRE for mutual authentication. EC P-384 CA key, trust domain `jupiter.cluster.local`, deployed into `spire` namespace with `system-cluster-critical` (server) and `system-node-critical` (agent) priority classes. SPIRE issues identities but does not enforce anything on its own — `authentication.mode: required` rules in `CiliumNetworkPolicy` resources are what give mTLS its actual security boundary. **This is why network policies are a prerequisite for getting real value out of the SPIRE deployment.**

### Branch for this work

`claude/cilium-network-policies` — based off `main`, no commits yet beyond this plan file.

---

## Process

1. **Inventory** — ran an exhaustive Explore agent across `kubernetes/apps/` to map every namespace, every app, every cross-namespace flow inferred from HelmRelease values, ExternalSecret references, ConfigMaps, and CiliumEnvoyConfig resources.
2. **Plan design** — ran a Plan agent with the full dependency map and a strict set of constraints (must not break Volsync, CNPG replication, Rook-Ceph CSI, external-secrets, Flux, Prometheus scraping) to produce a phased rollout plan.
3. **Synthesis** — distilled the plan into actionable phases with explicit risk callouts and verification commands.

---

## Findings

### Namespaces in the cluster (18)

`ai`, `auth`, `cert-manager`, `database`, `downloads`, `external-secrets`, `flux-system`, `games`, `kube-system`, `media`, `network`, `observability`, `openebs-system`, `rook-ceph`, `self-hosted`, `spire` (added by cilium-spire-mtls branch), `system-upgrade`, `volsync-system`.

### Critical cross-namespace flow map

**Universal flows** (every namespace participates):
- `*` → `kube-system/coredns` UDP/TCP 53 (DNS)
- `observability/prometheus` → `*` (scraping on metric ports)
- `observability/fluent-bit` reads `/var/log/containers` on nodes (host-level, not pod-to-pod)
- `external-secrets` operator writes Secrets via K8s API (RBAC-controlled, not policy-controlled)
- `kube-system/metrics-server` → kubelet on host nodes (10250/10255)

**Database tier (`database` namespace)** — highest fan-in in the cluster:
- All app namespaces → `database/redspot` (CNPG postgres) TCP 5432
- `self-hosted/paperless`, `self-hosted/nocodb` → `database/hindwing` (Dragonfly/Redis) TCP 6379
- `media/booklore` → `database/mariadb` TCP 3306
- CNPG → external `s3.us-west-001.backblazeb2.com` (barman backups)

**Storage (`rook-ceph` namespace)**:
- `auth/pocket-id`, `self-hosted/nocodb`, `self-hosted/rxresume` → RGW TCP 80 (S3)
- Volsync mover pods (spawned in app namespaces) → RGW TCP 80
- ⚠️ **Ceph daemons (OSD/MON/MGR) run with `network.provider: host`** — Cilium policies cannot see this traffic. Policies on `rook-ceph` only affect operator, CSI provisioners, RGW pods, and the toolbox.

**Observability**:
- `grafana` → `prometheus:9090`, `alertmanager:9093`, `victoria-logs:9428` (intra)
- `gatus` → `database:5432`, `games:25565`, `prometheus:9090`, `alertmanager:9093`
- `gatus` k8s-sidecar watches ConfigMaps cluster-wide (K8s API)
- `fluent-bit` → `victoria-logs:9428` (intra)
- `rook-ceph` host-network MGR → `alertmanager`, `prometheus`, `grafana` (appears as `host` entity in Cilium)
- `unpoller`, `snmp-exporter`, `blackbox-exporter` → LAN devices (UniFi, NAS) — egress to world

**Network/ingress (`network` namespace)**:
- `kube-system/cilium-gateway-external-auth` → `auth/tinyauth:3000` (CiliumEnvoyConfig external auth webhook)
- `cloudflared` → Cloudflare (HTTPS + QUIC/UDP 7844), → kube-system gateway ClusterIPs
- `external-dns` → Cloudflare API
- `smtp-relay` ← `auth/pocket-id`, possibly downloads/self-hosted on TCP 25
- `ingress-nginx` (external + internal) → all app backends
- `tailscale-operator` creates proxy StatefulSets in various namespaces; control-plane egress to `*.tailscale.com`

**AI namespace**:
- `ai/open-webui` → `ai/ollama:11434`
- `ai/paperless-ai` → `ai/ollama:11434`
- `ai/paperless-ai` → `self-hosted/paperless:8000`
- `ai/ollama` → world (model registry pulls)

**Volsync**:
- `volsync-system/volsync` controller → K8s API only (manages ReplicationSource CRs)
- Mover pods spawn in source namespace as Jobs with label `app.kubernetes.io/created-by: volsync`
- Mover pods → external S3 (Backblaze B2) and/or → `rook-ceph` RGW

**External secrets**:
- `external-secrets` operator → 1Password Connect pod (intra-namespace, port 80)
- 1Password Connect → `*.1password.com` (egress HTTPS)

**Games**:
- `games/mc-router` watches K8s Services via API (uses `IN_KUBE_CLUSTER: true`)
- `games` → world (mod downloads from CurseForge, Maven during pod startup)
- Some modpacks → `database/redspot:5432`
- `observability/gatus` → `games:25565` (TCP health checks)

**Flux**:
- `flux-system` → GitHub, OCI registries (ghcr.io, docker.io, quay.io, registry.k8s.io), Helm chart hosts (`charts.cilium.io`, `prometheus-community.github.io`, `bjw-s.github.io`, etc.)
- Flux → K8s API to apply resources in all namespaces (RBAC, not network policy)

---

## Important Callouts (READ BEFORE WRITING ANY YAML)

### Labels to verify against the live cluster

Before writing any cross-namespace selector, run these and adjust the plan if labels differ from what's documented:

```bash
# CNPG pods — expected: cnpg.io/cluster: redspot
kubectl get pods -n database --show-labels | grep redspot

# Dragonfly pods — expected: app: hindwing
kubectl get pods -n database --show-labels | grep hindwing

# MariaDB pods — expected: app.kubernetes.io/name: mariadb
kubectl get pods -n database --show-labels | grep mariadb

# Cilium gateway proxy pods — CRITICAL: verify label name and value
# May be gateway.networking.k8s.io/gateway-name OR cilium.io/gateway
# Adjust Policy 1.4 (allow-gateway-ingress) before applying
kubectl get pods -n kube-system --show-labels | grep gateway

# Volsync mover pod label — expected: app.kubernetes.io/created-by: volsync
# Trigger a manual snapshot if no mover is running and check labels
kubectl get pods -A --show-labels | grep volsync
```

### Rook-Ceph host networking exception

The Rook cluster HelmRelease sets `network.provider: host`. This means OSDs, MONs, and MGR daemons are host-networked. Cilium will not see their traffic as pod-to-pod. Policies on `rook-ceph` only affect:
- The Rook operator pod
- CSI provisioners (`rook-csi-rbdplugin-provisioner`, `rook-csi-cephfsplugin-provisioner`)
- RGW pods (`ceph-objectstore`) — serve port 80
- The toolbox pod

Do not attempt to govern OSD replication or MON quorum traffic with CiliumNetworkPolicy. The CSI node-plugin DaemonSet that runs on each node communicates with kubelet via Unix socket on the host — not network-policy-relevant.

### Cilium DNS proxy required for Phase 4

FQDN policies (`toFQDNs`) require Cilium's DNS proxy to be active. Verify with:

```bash
cilium status | grep -i dns
# or
kubectl -n kube-system exec ds/cilium -- cilium status | grep -i 'dns proxy'
```

The current config has `dns:query` in Hubble metrics which strongly implies the proxy is running, but confirm before relying on FQDN rules.

### Cilium policy audit mode

If supported in 1.19, run policies in shadow mode to log drops without enforcing. Check:

```bash
cilium config show | grep -i audit
```

If `policy-audit-mode` is available, set it before applying Phase 3 policies and watch Hubble for 24h before flipping enforcement on.

### Webhook namespaces with `failurePolicy: Fail`

`cert-manager` and `external-secrets` have admission webhooks with `failurePolicy: Fail`. If the webhook pod is unreachable, **resource creation fails cluster-wide**. Both must include `fromEntities: kube-apiserver` ingress rules. Apply these namespaces during a maintenance window and temporarily flip webhook `failurePolicy: Ignore` if you need to recover.

### LoadBalancer-exposed services

The following pods are reachable from outside the cluster via LoadBalancer IPs. Cilium sees external clients as the `world` entity:
- `downloads/qbittorrent` — port 61267 (incoming BitTorrent peers)
- `media/plex` — port 32400 (Plex clients)
- `database/hindwing` — Dragonfly is `type: LoadBalancer` with external-dns annotation `redis.internal`. **Audit who uses this LAN-exposed Redis endpoint before locking down database** — may want to remove the LoadBalancer type entirely.
- `games/*` — Minecraft servers on 25565 (via mc-router LoadBalancer)

---

## Phased Implementation Plan

### Phase 1 — Cluster-wide foundations (zero risk, apply first)

Four `CiliumClusterwideNetworkPolicy` resources. Since no namespace policies exist yet, these are purely additive and cannot break anything.

**File location:** `kubernetes/apps/kube-system/cilium/policies/`

Add a new Flux Kustomization stanza in `kubernetes/apps/kube-system/cilium/ks.yaml` for `cilium-policies` that depends on `cilium-config`:

```yaml
---
apiVersion: kustomize.toolkit.fluxcd.io/v1
kind: Kustomization
metadata:
  name: &app cilium-policies
  namespace: &ns kube-system
spec:
  targetNamespace: *ns
  dependsOn:
    - name: cilium-config
      namespace: *ns
  path: kubernetes/apps/kube-system/cilium/policies
  prune: true
  sourceRef:
    kind: GitRepository
    name: flux-system
    namespace: flux-system
  wait: true
  interval: 30m
  retryInterval: 1m
  timeout: 5m
```

**Policies to create:**

#### 1.1 — `allow-dns-egress.yaml`

```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideNetworkPolicy
metadata:
  name: allow-dns-egress
spec:
  endpointSelector: {}
  egress:
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s-app: kube-dns
      toPorts:
        - ports:
            - port: "53"
              protocol: UDP
            - port: "53"
              protocol: TCP
          rules:
            dns:
              - matchPattern: "*"
```

#### 1.2 — `allow-prometheus-scrape-ingress.yaml`

```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideNetworkPolicy
metadata:
  name: allow-prometheus-scrape-ingress
spec:
  endpointSelector: {}
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: observability
            app.kubernetes.io/name: prometheus
```

Broad on purpose — metric ports vary per app, and Prometheus is internal-only.

#### 1.3 — `allow-metrics-server-egress.yaml`

```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideNetworkPolicy
metadata:
  name: allow-metrics-server-egress
spec:
  endpointSelector:
    matchLabels:
      k8s:io.kubernetes.pod.namespace: kube-system
      app.kubernetes.io/name: metrics-server
  egress:
    - toEntities:
        - host
        - remote-node
      toPorts:
        - ports:
            - port: "10250"
              protocol: TCP
            - port: "10255"
              protocol: TCP
```

#### 1.4 — `allow-gateway-ingress.yaml`

```yaml
apiVersion: cilium.io/v2
kind: CiliumClusterwideNetworkPolicy
metadata:
  name: allow-gateway-ingress
spec:
  endpointSelector: {}
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            gateway.networking.k8s.io/gateway-name: external
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            gateway.networking.k8s.io/gateway-name: external-auth
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            gateway.networking.k8s.io/gateway-name: internal
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            gateway.networking.k8s.io/gateway-name: internal-auth
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            gateway.networking.k8s.io/gateway-name: tailscale
```

⚠️ **Verify the gateway pod label name before applying this one.** May be `cilium.io/gateway` instead.

#### 1.5 — `kustomization.yaml`

```yaml
# yaml-language-server: $schema=https://json.schemastore.org/kustomization
---
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization
resources:
  - allow-dns-egress.yaml
  - allow-prometheus-scrape-ingress.yaml
  - allow-metrics-server-egress.yaml
  - allow-gateway-ingress.yaml
```

---

### Phase 2 — Low-risk namespaces (apply in order)

Each namespace gets a single `CiliumNetworkPolicy` placed alongside the existing app manifests. Default-deny via `endpointSelector: {}`, then explicit intra-namespace allow + cross-namespace allows + DNS + kube-apiserver where needed.

**Rollout order:**

1. **`system-upgrade`** — Only tuppr. Allow intra + DNS + kube-apiserver + world (for GitHub upgrade checks).
2. **`openebs-system`** — Hostpath provisioner. Allow intra + DNS + kube-apiserver + host entity.
3. **`volsync-system`** — Controller only. Allow intra + DNS + kube-apiserver.
4. **`cert-manager`** ⚠️ — Webhook `failurePolicy: Fail`. Must include `fromEntities: kube-apiserver` ingress. Apply during maintenance window. Egress to world for ACME (restrict to FQDN in Phase 4).
5. **`ai`** — Allow intra + DNS + egress to `self-hosted/paperless:8000` + world for model pulls.
6. **`games`** — Allow intra + DNS + kube-apiserver (mc-router watches Services) + ingress from `observability/gatus:25565` + ingress from world on :25565 (mc-router LoadBalancer) + egress to `database/redspot:5432` (some modpacks) + world for mod downloads.
7. **`external-secrets`** ⚠️ — Same webhook caution as cert-manager. Egress to world for 1Password (restrict in Phase 4).

For each: monitor `hubble observe --verdict DROPPED --namespace <ns> --follow` for at least an hour before moving on.

---

### Phase 3 — Complex namespaces (24h soak between each)

Apply one at a time, watch Hubble for drops, validate critical flows manually before proceeding.

**Rollout order (lowest blast radius first):**

1. **`observability`** — Complex internal graph. Intra-allow covers grafana↔prometheus↔alertmanager↔victoria-logs. Add `fromEntities: host` ingress (rook-ceph host-network MGR pods reach alertmanager/prometheus/grafana this way). Egress to `database/redspot:5432` (gatus), `games:25565` (gatus health checks), world (unpoller, snmp, blackbox, alertmanager external webhooks), kube-apiserver (gatus k8s-sidecar).

2. **`auth`** — tinyauth is in the request path for every external-auth route. The Cilium gateway → tinyauth path is covered by cluster-wide policy 1.4, but verify with Hubble. Egress to `database/redspot:5432`, `rook-ceph` RGW :80, `network/smtp-relay:25`.

3. **`network`** — cloudflared is the inbound path for all external HTTPS traffic. Egress to `kube-system` ports 80/443 (gateway proxying) + DNS + kube-apiserver + world (Cloudflare, Tailscale, external SMTP). Ingress from auth/downloads/self-hosted to smtp-relay on :25.

4. **`self-hosted`** — Many apps → `database/redspot:5432` + `database/hindwing:6379` + `rook-ceph` RGW :80. Ingress from `ai` (paperless-ai → paperless:8000). World egress kept until Phase 4.

5. **`media`** — Postgres + MariaDB + world (Plex LoadBalancer ingress on :32400, metadata scraping, NFS to nas.internal). Egress to `downloads` :80 (Seerr/Maintainerr → arr apps).

6. **`downloads`** — Complex intra-namespace graph (prowlarr→arrs→qbittorrent→autobrr→cross-seed→...). Intra-allow handles all of it. Add ingress from world on :61267 (qbittorrent LB). Egress to `database/redspot:5432` + world (trackers, IRC, peers — FQDN not practical here, leave as world).

7. **`database`** ⚠️ HIGHEST BLAST RADIUS in Phase 3 ordering. CNPG primary/replica traffic on :5432 is intra-namespace (covered by intra-allow). Dragonfly emulated cluster mode is also intra-namespace. Ingress from every app namespace that needs each backend (postgres/dragonfly/mariadb) on the appropriate ports. Egress to world for barman backups (restrict in Phase 4).

8. **`rook-ceph`** ⚠️ APPLY LAST. Bad policy here breaks PVC provisioning cluster-wide. Allow intra + `fromEntities: host` (CSI loops, Ceph daemon callbacks) + ingress on :80 from auth/self-hosted/downloads/media (RGW S3 consumers + Volsync movers) + ingress from `kube-system` (CSI driver). Egress: DNS + kube-apiserver + host.

For each namespace policy, the template is:

```yaml
apiVersion: cilium.io/v2
kind: CiliumNetworkPolicy
metadata:
  name: default-deny
  namespace: <ns>
spec:
  endpointSelector: {}
  ingress:
    - fromEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: <ns>
    # plus specific cross-namespace allows
  egress:
    - toEndpoints:
        - matchLabels:
            k8s:io.kubernetes.pod.namespace: kube-system
            k8s-app: kube-dns
      toPorts:
        - ports:
            - port: "53"
              protocol: UDP
            - port: "53"
              protocol: TCP
    - toEntities:
        - kube-apiserver
    # plus specific cross-namespace + world allows
```

---

### Phase 4 — FQDN egress (replaces `world` rules)

Requires Cilium DNS proxy. Each `toFQDNs` rule must be paired with a matching DNS `matchName`/`matchPattern` rule in the same egress section so the proxy populates the IP cache.

**Pattern:**

```yaml
egress:
  - toFQDNs:
      - matchName: "api.github.com"
    toPorts:
      - ports:
          - port: "443"
            protocol: TCP
  - toEndpoints:
      - matchLabels:
          k8s:io.kubernetes.pod.namespace: kube-system
          k8s-app: kube-dns
    toPorts:
      - ports:
          - port: "53"
            protocol: UDP
          - port: "53"
            protocol: TCP
        rules:
          dns:
            - matchName: "api.github.com"
```

**Per-namespace FQDN allowlists:**

| Namespace | FQDNs |
|---|---|
| `flux-system` | `github.com`, `api.github.com`, `raw.githubusercontent.com`, `ghcr.io`, `*.ghcr.io`, `*.pkg.github.com`, `*.docker.io`, `quay.io`, `registry.k8s.io`, plus all HelmRepository hosts in `kubernetes/flux/meta/repositories/helm/` (cilium, prometheus-community, bjw-s, etc.) |
| `external-secrets` | `*.1password.com`, `my.1password.com` |
| `database` (CNPG pods only, selector `cnpg.io/cluster: redspot`) | `s3.us-west-001.backblazeb2.com` |
| `network` (cloudflared) | `*.cloudflare.com`, `api.cloudflare.com`, `*.cloudflareaccess.com` — :443 TCP and :7844 UDP |
| `network` (external-dns) | `api.cloudflare.com` :443 |
| `network` (tailscale-operator) | `controlplane.tailscale.com`, `*.tailscale.io`, `*.tailscale.com` :443 |
| `network` (smtp-relay) | External SMTP relay FQDN (read from `smtp-relay-secret`) :587 |
| `cert-manager` | `acme-v02.api.letsencrypt.org`, `*.api.letsencrypt.org`, `api.cloudflare.com` (DNS-01 challenge) :443 |
| `system-upgrade` | `github.com`, `api.github.com`, `ghcr.io`, `factory.talos.dev` :443 |
| Volsync movers (separate policy per namespace, selector `app.kubernetes.io/created-by: volsync`) | `*.backblazeb2.com` :443 + `rook-ceph` RGW :80 |

---

## Sequencing & Rollout

1. Apply Phase 1 cluster-wide policies. No risk — purely additive.
2. Verify with Hubble for an hour. Look for any unexpected drops.
3. Phase 2 namespaces in order, one at a time, ~1 hour each.
4. Phase 3 namespaces in the listed order, **24h soak between each**. `rook-ceph` is last.
5. Phase 4 FQDN policies, one namespace at a time. Replace world egress rules.

### Hubble queries

```bash
# Watch for drops in a specific namespace
hubble observe --verdict DROPPED --namespace <ns> --follow

# Watch for all drops cluster-wide
hubble observe --verdict DROPPED --follow

# Find which pods are dropping traffic and to where
hubble observe --verdict DROPPED --last 1h -o table | sort | uniq -c

# Specifically check policy verdict
hubble observe --verdict DROPPED --label "k8s:io.kubernetes.pod.namespace=<ns>" --follow
```

### Rollback

```bash
# Instantly restore open access for a namespace
kubectl delete cnp -n <ns> default-deny

# Or revert via git
git revert <commit-sha>
flux reconcile kustomization cluster-apps
```

Cluster-wide policies (Phase 1) are safe to leave permanently.

---

## Implementation Order Summary

```
Phase 1: kube-system/cilium/policies/  (4 CiliumClusterwideNetworkPolicy + ks.yaml stanza)
Phase 2: system-upgrade → openebs-system → volsync-system → cert-manager → ai → games → external-secrets
Phase 3: observability → auth → network → self-hosted → media → downloads → database → rook-ceph
Phase 4: FQDN egress per namespace, replacing world rules
```

---

## Once Network Policies Are In Place

The SPIRE deployment on `claude/cilium-spire-mtls` becomes immediately useful. Add `authentication.mode: required` to specific `CiliumNetworkPolicy` ingress rules to enforce mTLS on sensitive flows:

```yaml
ingress:
  - fromEndpoints:
      - matchLabels:
          k8s:io.kubernetes.pod.namespace: self-hosted
    authentication:
      mode: required   # both sides must present valid SPIFFE certs
    toPorts:
      - ports:
          - port: "5432"
            protocol: TCP
```

Start with the database namespace ingress rules. Pod A literally cannot connect to pod B on port 5432 unless both have valid SPIFFE identities issued by the SPIRE server. This is the zero-trust payoff.

---

## File Layout Recap

```
kubernetes/apps/kube-system/cilium/
├── app/
│   ├── helmrelease.yaml
│   ├── helm-values.yaml
│   └── kustomization.yaml
├── config/
│   ├── l2.yaml
│   ├── l3.yaml
│   ├── pool.yaml
│   ├── vip.yaml
│   └── kustomization.yaml
├── gateway/
│   └── ...
├── policies/                          ← NEW (Phase 1)
│   ├── allow-dns-egress.yaml
│   ├── allow-prometheus-scrape-ingress.yaml
│   ├── allow-metrics-server-egress.yaml
│   ├── allow-gateway-ingress.yaml
│   ├── kustomization.yaml
│   └── PLAN.md                        ← THIS FILE
└── ks.yaml                            ← add cilium-policies Kustomization

kubernetes/apps/<namespace>/<app>/app/
└── ciliumnetworkpolicy.yaml           ← Phase 2-3 per-namespace policies
```

Per-namespace policies should be added to each app's `app/kustomization.yaml` resources list.
