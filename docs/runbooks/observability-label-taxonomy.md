# Observability label taxonomy

Container logs in VictoriaLogs use the normalized labels below. Metrics in
VictoriaMetrics retain exporter labels by default, with an experimental
Service flag that promotes Kubernetes discovery metadata for selected
application scrapes.

## Normalized log labels

- `namespace`: Kubernetes namespace from the enriched log record.
- `pod`: Kubernetes Pod name, when Pod metadata is available.
- `container`: Kubernetes container name, when container metadata is available.
- `app`: Application name. Precedence is exactly `app.kubernetes.io/name`,
  then `app`, then `k8s-app`.
- `app_instance`: Value of `app.kubernetes.io/instance`.
- `component`: Value of `app.kubernetes.io/component`.
- `part_of`: Value of `app.kubernetes.io/part-of`.
- `flux_kustomization`: Value of `kustomize.toolkit.fluxcd.io/name`, when
  present on Kubernetes metadata.
- `helmrelease`: Value of `helm.toolkit.fluxcd.io/name`, when present on
  Kubernetes metadata.
- `stream`: Container runtime stream, normally `stdout` or `stderr`.

Missing log labels mean that the source did not provide usable metadata; they
do not imply a collector failure.

## Where labels come from

- Logs normalize fields from Fluent Bit's Kubernetes-enriched record. Query the
  canonical names above, not Fluent Bit's intermediate nested record paths.
- The `cluster` vmagent external label is attached to stored metrics.
- Metrics from Services without the experimental flag remain exporter- and
  target-specific. No canonical labels are added unless the discovered Service
  carries the experimental flag described below.
- Static `VMProbe` targets do not have Kubernetes discovery metadata. App
  probes set truthful `targets.static.labels` (`namespace`, `app`) in Git.
  Heterogeneous probes (e.g. `devices`, `nfs`) set `namespace` only — never
  invent `pod`/`container` or Flux provenance. The metrics-wide `cluster`
  label still applies.
- Flux-native labels exist only on top-level Flux-managed objects. They are not
  automatically copied into Pod templates, so `flux_kustomization` and
  `helmrelease` are commonly unavailable on container-log Pods.

## Metrics target labels (Service scrapes)

Application metrics taxonomy enrichment is **default-on** for Service-backed
scrapes. vmagent promotes discovery metadata onto taxonomy labels whenever
`__meta_kubernetes_service_name` is present, unless the Service opts out with:

```yaml
observability.homelab.zebernst.dev/canonical-labels: "false"
```

Current opt-outs (exporter Services whose identity is the scraper, not the
series subject):

| Namespace | Services |
|-----------|----------|
| `observability` | `kube-state-metrics`, `node-exporter` |

Static `VMProbe` targets, kubelet, and cAdvisor are not Service scrapes, so they
remain unaffected by this path.

For Service-backed targets (without opt-out), vmagent promotes metadata that
exists at discovery time:

- `namespace` from the Kubernetes namespace.
- `pod` and `container` from Pod discovery metadata, when present.
- `app` from application labels. At both the Service and Pod levels, precedence
  is `app.kubernetes.io/name`, then `app`, then `k8s-app`; Pod values take
  precedence over Service values.
- `app_instance`, `component`, and `part_of` from the corresponding recommended
  Kubernetes labels. Pod values take precedence over Service values.
- `helmrelease` from Flux's native `helm.toolkit.fluxcd.io/name` Service label.
- `flux_kustomization` from the native
  `kustomize.toolkit.fluxcd.io/name` Service label only when it is actually
  present. Helm-rendered Services commonly do not carry this label, so its
  absence is expected.

Missing source metadata stays absent. The relabeling does not synthesize
workload or controller identity and does not forge Flux ownership labels.

Target labels are fill-in only. On conflict with sample labels, vmagent
restores `exported_<label>` → `<label>` for the taxonomy identity set before
remote write, so stored metrics keep sample identity. Do not rely on
`exported_namespace` / `exported_pod` / etc. in alerts or dashboards.

## kube-state-metrics label allowlist

`kube_pod_labels` / `kube_deployment_labels` / `kube_persistentvolumeclaim_labels`
only export an allowlisted set of Kubernetes labels (not `[*]`).

**Keep**

- Taxonomy: `app.kubernetes.io/{name,instance,component,part-of}`, `app`, `k8s-app`
- Chart/pkg: `app.kubernetes.io/{managed-by,version,created-by,controller}`,
  `helm.sh/chart`, `chart`, `release`
- Flux: `helm.toolkit.fluxcd.io/{name,namespace}`,
  `kustomize.toolkit.fluxcd.io/{name,namespace}`,
  `fluxcd.controlplane.io/{name,namespace}`
- CNPG: `cnpg.io/cluster`, `instanceName`, `instanceRole`, `podRole` / `pvcRole`
- Rook/Ceph: `rook_cluster`, `rook-version`, `ceph_daemon_type`, `ceph-version`,
  `rook.io/operator-namespace`, `rook_file_system`, `rook_object_store`,
  `device-class`, `failure-domain`
- Other useful one-offs: `role`, `component`, `tier`, `svc`, Tailscale parent
  labels, Fission `functionName` / `functionNamespace` / env name+ns,
  `io.cilium/app`, OpenEBS component, a few control-plane helpers
- PVCs also: `volsync.backube/cleanup`, Prometheus Operator PVC labels

**Drop (still)**

High-cardinality controller noise and IDs: `pod-template-hash`,
`controller-revision-hash`, `controller-uid`, batch/job UIDs,
`apps.kubernetes.io/pod-index`, `statefulset.kubernetes.io/pod-name`,
`functionUid`, `environmentUid`, `ceph_daemon_id` / `ceph-osd-id`,
`topology-location-*`, Helm `heritage`, and other one-off churn keys.

Kubelet scrapes separately drop `uid` / container `id` labels — leave those
drops in place when editing VictoriaMetrics values.

## Incident queries

In Grafana Explore, select the VictoriaLogs datasource and use LogsQL stream
filters. Grafana supplies the selected time range.

```text
{namespace="self-hosted",app="nominatim"}
```

Narrow an application to a container and runtime stream, then search its
message:

```text
{namespace="self-hosted",app="nominatim",container="app",stream="stderr"} error
```

Count matching logs by Pod and stream:

```text
{namespace="self-hosted",app="nominatim"} | stats by (pod, stream) count()
```

For metrics, start with labels native to the metric source. cAdvisor container
metrics provide `namespace`, `pod`, and `container`, so a workload can be
selected by its native Pod name:

```promql
sum by (pod, container) (
  rate(container_cpu_usage_seconds_total{
    cluster="jupiter",
    namespace="self-hosted",
    pod=~"nominatim-.*",
    container="app"
  }[5m])
)
```

A flagged application target can be selected with promoted target labels:

```promql
up{
  cluster="jupiter",
  namespace="self-hosted",
  app="atuin",
  helmrelease="atuin"
}
```

Do not assume `flux_kustomization` exists on these Helm-rendered Services.
Native cAdvisor metrics are outside the experimental gate and should continue
to use their native labels, as in the container CPU query above.

## Grafana logs dashboard

The **Logs taxonomy** dashboard (folder `Logs`, uid `logs-taxonomy`) is
provisioned via ConfigMap `grafana-logs-taxonomy-dashboard` and the Grafana
dashboard sidecar. Variables cascade on canonical stream fields only:

`namespace` → `app` → `pod` / `container` / `stream`, plus an optional
textbox `search` appended as a LogsQL fragment (leave empty for no extra
filter).

Panel queries use `{namespace="$namespace", app="$app", …}` (VictoriaLogs
expands multi-value variables via `in(...)`) — never Fluent Bit intermediate
`k_*` paths.

## Grafana Correlations (logs ↔ metrics)

Grafana [Correlations](https://grafana.com/docs/grafana/latest/administration/correlations/)
turn a field on one Explore result into a query on another datasource. They are
provisioned on the Prometheus and VictoriaLogs datasources in
`kubernetes/apps/observability/grafana/app/helmrelease.yaml` for the taxonomy
labels that are routinely present after the Fluent Bit rename: `app`,
`namespace`, and `pod`. Links only appear when every `${var}` in the target
query is present on the clicked row — do not require `helmrelease` /
`flux_kustomization` on log rows.

Provisioned datasource UIDs:

| Datasource   | UID           |
|--------------|---------------|
| Prometheus   | `prometheus`  |
| VictoriaLogs | `victorialogs` |

### Preferred links

| Direction | Source field | Target |
|-----------|--------------|--------|
| Logs → metrics | `pod` | cAdvisor CPU for `${namespace}` / `${pod}` |
| Logs → metrics | `app` | `up{namespace, app}` (flagged Services) |
| Logs → metrics | `namespace` | `up{namespace, app!=""}` |
| Metrics → logs | `pod` / `app` / `namespace` | LogsQL stream filter on those labels |

### Verify in Explore

1. Open **Explore** → VictoriaLogs, run `{app="atuin"}` (or any app with
   recent logs).
2. Expand a log line and use the correlation link on `pod` / `app` /
   `namespace` (opens split Explore on Prometheus).
3. From a Prometheus table/series with those labels, use the reverse links
   into VictoriaLogs.

To change the links, edit the datasource `correlations:` blocks in Git rather
than recreating them only in the UI.

## VictoriaLogs alert rules (vmalert)

Log-based rules live in ConfigMaps labeled `vmalert.io/rule: "true"` and are
loaded by the logs `vmalert` instance (`--rule.defaultRuleType=vlogs`). Still
set the group field explicitly:

```yaml
groups:
  - name: example
    type: vlogs
    rules:
      - alert: ExampleAppError
        expr: |
          sum by (app) (count_over_time({app="example"} |~ "(?i)error"[5m])) > 0
        labels:
          severity: critical
          category: vlogs
        annotations:
          summary: "{{ $labels.app }} is logging errors"
```

Conventions:

- Prefer stream filters on canonical labels (`app`, `namespace`, `container`,
  `pod`), not Fluent Bit intermediate paths (`k_*` / nested record keys).
- Aggregate (`sum by` / `stats by`) only on labels you need in annotations.
  After `sum by (app)`, only `$labels.app` exists — do not reference
  `$labels.container` or other dropped dimensions.
- Use `category: vlogs` (not `category: logs`) so log alerts stay distinct from
  metrics rules in Alertmanager routing and silence filters.

## Scope boundaries

This taxonomy does not cover tracing, synthesized workload or controller
identity, or admission/per-workload patches that add Pod-level Flux provenance.

## References

- [VictoriaLogs LogsQL](https://docs.victoriametrics.com/victorialogs/logsql/)
- [VictoriaLogs Grafana integration](https://docs.victoriametrics.com/victorialogs/integrations/grafana/)
- [Prometheus querying basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Grafana Correlations](https://grafana.com/docs/grafana/latest/administration/correlations/)
- [Create a correlation](https://grafana.com/docs/grafana/latest/administration/correlations/create-a-new-correlation/)
