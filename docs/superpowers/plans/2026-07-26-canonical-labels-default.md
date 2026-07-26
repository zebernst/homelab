# Canonical Labels Default-On Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Service-scrape taxonomy enrichment default-on, with an explicit opt-out on kube-state-metrics and node-exporter, and remove all experimental opt-in flags.

**Architecture:** Replace the experimental Service label gate in `vmagent` `globalScrapeRelabelConfigs` with `__meta_kubernetes_service_name` plus opt-out label `observability.homelab.zebernst.dev/canonical-labels` matching `(|true)`. Opt out the two exporter Services via chart values. Delete the sixteen application opt-in flags. Update runbook and epic tracking.

**Tech Stack:** Flux GitOps, VictoriaMetrics k8s-stack HelmRelease, kube-state-metrics / prometheus-node-exporter subcharts, PromQL live validation.

**Spec:** `docs/superpowers/specs/2026-07-26-canonical-labels-default-design.md`

## Global Constraints

- Enrich only Service-backed scrapes (`__meta_kubernetes_service_name` non-empty).
- Opt-out label: `observability.homelab.zebernst.dev/canonical-labels: "false"` (meta key `observability_homelab_zebernst_dev_canonical_labels`).
- Enrichment regex: `(.+);(|true);(.+)` with value replacement `$3`.
- Required opt-outs: kube-state-metrics (`customLabels`) and node-exporter (`service.labels`).
- Do not change remote-write sample-wins restore or Fluent Bit log taxonomy.
- Work from a fresh branch/worktree off `main`; do not commit unless the user asks (or a later task explicitly says to after user approval).

---

## File map

| File | Responsibility |
|------|----------------|
| `kubernetes/apps/observability/victoria-metrics/app/helmrelease.yaml` | Relabel gate change + KSM/node-exporter opt-out labels |
| Sixteen app `helmrelease.yaml` files listed in Task 2 | Remove experimental opt-in Service labels |
| `docs/runbooks/observability-label-taxonomy.md` | Document default-on + opt-out |
| `docs/superpowers/specs/2026-07-26-canonical-labels-default-design.md` | Already written; include in PR if uncommitted |
| Beads `homelab-1vb` / new child | Track work; update epic design bullets |

---

### Task 1: Switch vmagent gate + platform opt-outs

**Files:**
- Modify: `kubernetes/apps/observability/victoria-metrics/app/helmrelease.yaml` (`vmagent.spec.globalScrapeRelabelConfigs`, `kube-state-metrics`, `prometheus-node-exporter`)

**Interfaces:**
- Consumes: existing enrichment target labels (`namespace`, `pod`, `container`, `app`, `app_instance`, `component`, `part_of`, `helmrelease`, `flux_kustomization`) and precedence order
- Produces: default-on Service enrichment; opt-out meta label present on KSM and node-exporter Services

- [ ] **Step 1: Create branch/worktree from main**

```bash
cd /Users/zach/Developer/homelab
git fetch origin main
# Prefer worktree if using-git-worktrees skill; otherwise:
git checkout -b feat/canonical-labels-default origin/main
```

- [ ] **Step 2: Replace every experimental gate in `globalScrapeRelabelConfigs`**

For each enrichment rule currently shaped like:

```yaml
- action: replace
  sourceLabels:
    - __meta_kubernetes_service_label_experimental_homelab_zebernst_dev_canonical_labels
    - <DISCOVERY_LABEL>
  regex: true;(.+)
  replacement: $1
  targetLabel: <TARGET>
```

change to:

```yaml
- action: replace
  sourceLabels:
    - __meta_kubernetes_service_name
    - __meta_kubernetes_service_label_observability_homelab_zebernst_dev_canonical_labels
    - <DISCOVERY_LABEL>
  regex: (.+);(|true);(.+)
  replacement: $3
  targetLabel: <TARGET>
```

Apply to all rules in that block (namespace, app precedence chain, app_instance, component, part_of, helmrelease, flux_kustomization, pod, container, and Pod-level app overrides). Leave `inlineRelabelConfig` (exported_* restore) untouched.

- [ ] **Step 3: Opt out kube-state-metrics and node-exporter Services**

Under `kube-state-metrics:` add:

```yaml
customLabels:
  observability.homelab.zebernst.dev/canonical-labels: "false"
```

Under `prometheus-node-exporter:` add:

```yaml
service:
  labels:
    observability.homelab.zebernst.dev/canonical-labels: "false"
```

(If `service:` already exists for node-exporter, merge `labels` into it.)

- [ ] **Step 4: Sanity-check the YAML locally**

```bash
rg -n 'experimental_homelab_zebernst_dev_canonical_labels|observability_homelab_zebernst_dev_canonical_labels|canonical-labels' \
  kubernetes/apps/observability/victoria-metrics/app/helmrelease.yaml
```

Expected:
- Zero matches for `experimental_homelab_...`
- Many `observability_homelab_...` in `globalScrapeRelabelConfigs`
- Two `"false"` opt-outs under KSM `customLabels` and node-exporter `service.labels`

- [ ] **Step 5: Commit this task only if the user asked for commits; otherwise leave staged/unstaged for a single PR commit later**

Suggested message if committing:

```text
feat(observability): default-on canonical labels for Service scrapes
```

---

### Task 2: Remove experimental flags from application Services

**Files:**
- Modify (remove the label key entirely from Service labels):
  - `kubernetes/apps/self-hosted/atuin/app/helmrelease.yaml`
  - `kubernetes/apps/self-hosted/paperless/app/helmrelease.yaml`
  - `kubernetes/apps/self-hosted/dawarich/app/helmrelease.yaml`
  - `kubernetes/apps/observability/gatus/private/helmrelease.yaml`
  - `kubernetes/apps/observability/gatus/external/helmrelease.yaml`
  - `kubernetes/apps/downloads/autobrr/app/helmrelease.yaml`
  - `kubernetes/apps/downloads/bazarr/hd/helmrelease.yaml`
  - `kubernetes/apps/downloads/bazarr/uhd/helmrelease.yaml`
  - `kubernetes/apps/downloads/lidarr/app/helmrelease.yaml`
  - `kubernetes/apps/downloads/prowlarr/app/helmrelease.yaml`
  - `kubernetes/apps/downloads/qui/app/helmrelease.yaml`
  - `kubernetes/apps/downloads/radarr/app/hd/helmrelease.yaml`
  - `kubernetes/apps/downloads/radarr/app/uhd/helmrelease.yaml`
  - `kubernetes/apps/downloads/sonarr/app/hd/helmrelease.yaml`
  - `kubernetes/apps/downloads/sonarr/app/uhd/helmrelease.yaml`
  - `kubernetes/apps/downloads/unpackerr/app/helmrelease.yaml`

**Interfaces:**
- Consumes: Task 1 default-on gate (apps no longer need opt-in)
- Produces: repo with zero experimental canonical-labels flags

- [ ] **Step 1: Delete the experimental label from each Service**

Remove this line wherever it appears under Service labels:

```yaml
experimental.homelab.zebernst.dev/canonical-labels: "true"
```

Do not leave an empty `labels:` map if it becomes empty solely because of this key — keep any remaining labels; if `labels:` would be empty, remove the whole `labels:` block only when that matches surrounding chart structure.

- [ ] **Step 2: Verify repo-wide cleanup**

```bash
rg -n 'experimental\.homelab\.zebernst\.dev/canonical-labels' kubernetes docs || true
```

Expected: no matches (except possibly historical notes in agent transcripts outside the repo).

---

### Task 3: Update runbook + beads

**Files:**
- Modify: `docs/runbooks/observability-label-taxonomy.md` (section currently titled “Experimental metrics target labels”)
- Beads: create/close child under `homelab-1vb`; update epic design bullet

**Interfaces:**
- Consumes: policy from the design spec
- Produces: operator-facing docs matching live behavior

- [ ] **Step 1: Rewrite the metrics section**

Replace the experimental / flagged-Services table with:

- Title: “Metrics target labels (Service scrapes)”
- Default: all Service-backed scrapes get taxonomy enrichment
- Opt-out: `observability.homelab.zebernst.dev/canonical-labels: "false"` on the Service
- Current opt-outs: `kube-state-metrics`, `node-exporter`
- Non-Service scrapes (kubelet, cAdvisor, static VMProbe) remain unaffected
- Keep the existing precedence / Flux / sample-wins paragraphs (still accurate)

- [ ] **Step 2: Create and track the bead**

```bash
mise x -- bd create "Default-on canonical metrics labels (Service scrapes)" \
  --type task --priority 2 --parent homelab-1vb
# note the new id, e.g. homelab-1vb.9
```

Update epic `homelab-1vb` description: change the metrics enrichment bullet from experimental opt-in to default-on + opt-out.

- [ ] **Step 3: Commit docs/beads with the code change when opening the PR (user-approved commit)**

---

### Task 4: PR, merge follow-up, live validate

**Files:** none beyond prior tasks

- [ ] **Step 1: Open PR**

Include design spec path in the PR body. Summary bullets:

- Default-on canonical labels for Service scrapes
- Opt-out on kube-state-metrics + node-exporter
- Remove experimental flags from 16 apps
- Runbook update

- [ ] **Step 2: After merge + Flux upgrades vmagent / Services, validate**

```bash
QUERY_URL="http://vmsingle-vmks.observability.svc:8428"
# helper: kubectl run curl pod as in prior sessions

# Former pilot still labeled
query 'count(up{app="paperless"})'

# Unflagged Service scrape should now be able to carry app when discovery has it
# Pick any ServiceMonitor/VMServiceScrape app that never had the experimental flag
query 'count(up{namespace="cert-manager",app!=""})'

# KSM must NOT stamp app=kube-state-metrics onto kube_* series
query 'count(kube_pod_info{app="kube-state-metrics"}) or vector(0)'
# expect 0 (or only if sample itself had that label — should be ~0)

# node-exporter inert for taxonomy app
query 'count(node_cpu_seconds_total{app!=""}) or vector(0)'

# Live Services carry opt-out
kubectl -n observability get svc kube-state-metrics node-exporter \
  -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.metadata.labels.observability\.homelab\.zebernst\.dev/canonical-labels}{"\n"}{end}'
# expect: false / false
```

- [ ] **Step 3: Close the bead** with merge + validation notes

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Service-name gate + opt-out regex | Task 1 |
| Opt-out on KSM + node-exporter | Task 1 |
| Delete 16 experimental flags | Task 2 |
| Runbook rewrite | Task 3 |
| Epic/bead tracking | Task 3 |
| Live validation queries | Task 4 |
| Unchanged restore / log taxonomy / KSM allowlist | Task 1 leaves them alone |

## Self-review notes

- No TBD/placeholders.
- Replacement `$3` matches three sourceLabels; do not leave `$1` from the old two-label rules.
- Node-exporter chart key is `prometheus-node-exporter.service.labels`; KSM is `kube-state-metrics.customLabels`.
