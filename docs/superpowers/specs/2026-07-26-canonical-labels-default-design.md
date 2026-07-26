# Canonical metrics labels as Service-scrape default

Date: 2026-07-26  
Status: approved for implementation  
Related: epic `homelab-1vb`, runbook `docs/runbooks/observability-label-taxonomy.md`

## Goal

Make application metrics taxonomy enrichment the **default** for Service-backed
scrapes. Remove the experimental opt-in Service flag. Keep kubelet, cAdvisor,
static VMProbes, and exporter Services that describe *other* subjects (notably
kube-state-metrics) from being incorrectly stamped.

## Non-goals

- Pod-level Flux provenance on logs (still deferred as `homelab-1vb.8`)
- Changing Fluent Bit / VictoriaLogs taxonomy
- Changing remote-write sample-wins restore (`exported_*` → identity labels)
- Annotating every application Service

## Current behavior

`vmagent` `globalScrapeRelabelConfigs` promote discovery metadata onto taxonomy
labels only when the scraped Service has:

```yaml
experimental.homelab.zebernst.dev/canonical-labels: "true"
```

Sixteen application Services carry that flag today. Platform scrapes without it
are inert.

## Design

### Policy

| Scrape kind | Enrichment |
|-------------|------------|
| Service-backed scrape, no opt-out | **On** (default) |
| Service-backed scrape with opt-out `"false"` | Off |
| Non-Service scrapes (kubelet, cAdvisor, static VMProbe, etc.) | Off (no `__meta_kubernetes_service_name`) |

### Gate + opt-out

Each enrichment rule uses three source labels:

1. `__meta_kubernetes_service_name` — must be non-empty (Service scrape)
2. `__meta_kubernetes_service_label_observability_homelab_zebernst_dev_canonical_labels` — must be empty or `true` (not `false`)
3. The discovery value to copy (unchanged from today)

Regex shape (RE2):

```text
(.+);(|true);(.+)
```

Replacement for the copied value: `$3`.

Stable opt-out label on the Service:

```yaml
observability.homelab.zebernst.dev/canonical-labels: "false"
```

No opt-in label. Delete all
`experimental.homelab.zebernst.dev/canonical-labels` annotations/labels from
application HelmReleases.

### Required opt-outs

Set the opt-out on Services whose identity is the *scraper*, not the series
subject:

- `kube-state-metrics` (otherwise every `kube_*` series would get
  `app=kube-state-metrics`)
- `node-exporter` (keep current inert behavior for node scrapes)

Apply via `victoria-metrics-k8s-stack` Helm values (`customLabels` /
`service.labels` — whichever the chart wires onto the Service).

Other VictoriaMetrics / app Services may keep default-on; stamping
`app=vmsingle` (etc.) on their own metrics is correct.

### Unchanged

- App precedence: Service then Pod, `app.kubernetes.io/name` > `app` > `k8s-app`
- Flux: `helmrelease` / `flux_kustomization` from native toolkit Service labels
  only when present
- `inlineRelabelConfig` remote-write restore + `exported_*` labeldrop
- KSM `metricLabelsAllowlist` and kubelet uid/id drops

## Docs / tracking

- Rewrite runbook section “Experimental metrics target labels” → default Service
  scrape enrichment + opt-out table
- Update epic `homelab-1vb` design bullets (opt-in → default-on + opt-out)
- New bead under the epic for this change; close when merged and live-validated

## Validation

After Flux upgrades `vmagent`:

1. A former pilot (e.g. `up{app="paperless"}`) still has taxonomy labels without
   the experimental Service flag.
2. A previously unflagged Service-backed app scrape gains `app` / Flux labels
   when discovery metadata exists.
3. `kube_pod_labels` / `kube_*` series do **not** all carry
   `app="kube-state-metrics"`.
4. `node_cpu_*` (or equivalent) do not pick up unexpected taxonomy `app` from
   enrichment.
5. Kubelet/cAdvisor series remain without forged Flux labels from this path.
6. Grep the repo: no remaining `experimental.homelab.zebernst.dev/canonical-labels`.

## Rollout

Single PR from a fresh branch off `main`:

1. Relabel gate change + KSM/node-exporter opt-out in
   `kubernetes/apps/observability/victoria-metrics/app/helmrelease.yaml`
2. Remove experimental flags from the sixteen app HelmReleases
3. Runbook (+ epic/bead) updates
4. Merge, live-validate, close bead
