#!/usr/bin/env python3
"""Generate platform architecture graphs from Flux Kustomization dependsOn edges."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KS_GLOB = "kubernetes/**/ks.yaml"
DEFAULT_OUT_DIR = ROOT / "docs" / "architecture"
LAYER_CONFIG_PATH = DEFAULT_OUT_DIR / "tier-categories.yaml"
WORKLOAD_GROUP = "workloads"

# Upstream platforms included in collapsed views even when fan-out is smaller.
UPSTREAM_PLATFORMS = {
    "cert-manager/cert-manager",
    "cert-manager/cert-manager-issuers",
    "database/cloudnative-pg",
    "external-secrets/external-secrets",
    "flux-system/cluster-meta",
    "flux-system/cluster-apps",
    "kube-system/cilium",
    "kube-system/snapshot-controller",
    "observability/victoria-logs",
    "observability/victoria-metrics",
    "rook-ceph/rook-ceph",
}

PLATFORM_MIN_DEPENDENTS = 5

COMPONENT_EDGES = {
    "gatus": ("monitor", "observability/gatus"),
    "volsync": ("backup", "volsync-system/volsync"),
    "keda/nfs-scaler": ("scale", "kube-system/nfs-subdir-external-provisioner"),
}

METRICS_PLATFORM = "observability/victoria-metrics-operator"

MONITOR_BLOCK_KEYS = frozenset(
    {"serviceMonitor", "podMonitor", "ServiceMonitor", "PodMonitor"}
)
MONITOR_BOOL_KEYS = frozenset({"enablePodMonitor", "podMonitorEnabled"})
VM_SCRAPE_KINDS = frozenset({"VMServiceScrape", "VMPodScrape", "VMProbe"})
MONITOR_SUBSTANTIVE_KEYS = frozenset(
    {
        "endpoints",
        "endpoint",
        "labels",
        "interval",
        "selector",
        "namespaceSelector",
        "vm",
        "serviceName",
        "port",
        "path",
        "scheme",
        "relabelings",
        "metricRelabelings",
    }
)
APPS_GLOB = "kubernetes/apps/**/*"

DOMAIN_LABELS = {
    "ai": "AI",
    "auth": "Auth",
    "cert-manager": "Cert Manager",
    "database": "Database",
    "downloads": "Downloads",
    "external-secrets": "External Secrets",
    "fission": "Fission",
    "flux-system": "Flux",
    "games": "Games",
    "kube-system": "Kube System",
    "media": "Media",
    "network": "Network",
    "observability": "Observability",
    "openebs-system": "OpenEBS",
    "rook-ceph": "Rook Ceph",
    "self-hosted": "Self-Hosted",
    "system-upgrade": "System Upgrade",
    "volsync-system": "Volsync",
}


@dataclass
class Kustomization:
    node_id: str
    name: str
    namespace: str
    path: str
    deploy_deps: set[str] = field(default_factory=set)
    components: set[str] = field(default_factory=set)


@dataclass
class Edge:
    source: str
    target: str
    kind: str

    def key(self) -> tuple[str, str, str]:
        return (self.source, self.target, self.kind)


def load_kustomizations(root: Path, pattern: str) -> dict[str, Kustomization]:
    nodes: dict[str, Kustomization] = {}

    for path in sorted(root.glob(pattern)):
        with path.open() as handle:
            for doc in yaml.safe_load_all(handle):
                if not doc or doc.get("kind") != "Kustomization":
                    continue

                name = doc["metadata"]["name"]
                namespace = doc["metadata"]["namespace"]
                node_id = f"{namespace}/{name}"
                spec = doc.get("spec", {})

                ks = Kustomization(
                    node_id=node_id,
                    name=name,
                    namespace=namespace,
                    path=spec.get("path", ""),
                )

                for dep in spec.get("dependsOn") or []:
                    dep_ns = dep.get("namespace", namespace)
                    ks.deploy_deps.add(f"{dep_ns}/{dep['name']}")

                for component in spec.get("components") or []:
                    component = component.removeprefix("../../../../components/").removeprefix(
                        "../../../../../components/"
                    )
                    ks.components.add(component)

                nodes[node_id] = ks

    return nodes


def compute_tiers(nodes: dict[str, Kustomization]) -> dict[str, int]:
    memo: dict[str, int] = {}

    def tier(node_id: str, visiting: set[str] | None = None) -> int:
        if node_id in memo:
            return memo[node_id]
        if visiting is None:
            visiting = set()
        if node_id in visiting:
            return 0
        ks = nodes.get(node_id)
        if ks is None or not ks.deploy_deps:
            memo[node_id] = 0
            return 0
        visiting.add(node_id)
        value = 1 + max(tier(dep, visiting) for dep in ks.deploy_deps)
        visiting.remove(node_id)
        memo[node_id] = value
        return value

    for node_id in nodes:
        tier(node_id)
    return memo


def deploy_edges(nodes: dict[str, Kustomization]) -> list[Edge]:
    edges: list[Edge] = []
    for ks in nodes.values():
        for dep in ks.deploy_deps:
            edges.append(Edge(source=ks.node_id, target=dep, kind="deploy"))
    return edges


def build_path_index(nodes: dict[str, Kustomization]) -> list[tuple[str, str]]:
    return sorted(
        ((ks.path.rstrip("/"), ks.node_id) for ks in nodes.values() if ks.path),
        key=lambda item: len(item[0]),
        reverse=True,
    )


def match_node_id(
    file_path: Path,
    root: Path,
    path_index: list[tuple[str, str]],
) -> str | None:
    rel = file_path.relative_to(root).as_posix()
    for ks_path, node_id in path_index:
        if rel == ks_path or rel.startswith(f"{ks_path}/"):
            return node_id
    return None


def monitor_block_enabled(key: str, value: object) -> bool:
    if value is None:
        return False
    if key in MONITOR_BOOL_KEYS:
        return value is True
    if isinstance(value, bool):
        return value
    if not isinstance(value, dict):
        return False
    if value.get("enabled") is False or value.get("create") is False:
        return False
    if value.get("enabled") is True or value.get("create") is True:
        return True
    if key.lower() in {"servicemonitor", "podmonitor"}:
        if MONITOR_SUBSTANTIVE_KEYS & value.keys():
            return True
        return any(
            isinstance(item, dict) and ("endpoints" in item or "endpoint" in item)
            for item in value.values()
        )
    if key == "monitoring" and value.get("enabled") is True:
        return True
    return False


def monitoring_signals(document: object) -> list[str]:
    signals: list[str] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            kind = obj.get("kind")
            if kind in VM_SCRAPE_KINDS:
                signals.append(str(kind))

            for key, value in obj.items():
                if key in MONITOR_BOOL_KEYS and value is True:
                    signals.append(key)
                elif key in MONITOR_BLOCK_KEYS or key == "monitoring":
                    if monitor_block_enabled(key, value):
                        signals.append(key)
                else:
                    walk(value)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(document)
    return signals


def discover_metrics_targets(
    root: Path,
    nodes: dict[str, Kustomization],
) -> dict[str, set[str]]:
    path_index = build_path_index(nodes)
    targets: dict[str, set[str]] = defaultdict(set)

    for path in sorted(root.glob(APPS_GLOB)):
        if not path.is_file() or path.suffix not in {".yaml", ".yml"}:
            continue

        with path.open() as handle:
            try:
                documents = list(yaml.safe_load_all(handle))
            except yaml.YAMLError:
                continue

        for document in documents:
            if not document:
                continue
            signals = monitoring_signals(document)
            if not signals:
                continue

            node_id = match_node_id(path, root, path_index)
            if node_id is None:
                continue
            targets[node_id].update(signals)

    return targets


def component_edges(nodes: dict[str, Kustomization]) -> list[Edge]:
    edges: list[Edge] = []
    for ks in nodes.values():
        for component in ks.components:
            if component not in COMPONENT_EDGES:
                continue
            kind, platform = COMPONENT_EDGES[component]
            if kind == "monitor":
                edges.append(Edge(source=platform, target=ks.node_id, kind=kind))
            else:
                edges.append(Edge(source=ks.node_id, target=platform, kind=kind))
    return edges


def metrics_edges(metrics_targets: dict[str, set[str]]) -> list[Edge]:
    edges: list[Edge] = []
    for node_id in sorted(metrics_targets):
        edges.append(
            Edge(
                source=METRICS_PLATFORM,
                target=node_id,
                kind="metrics",
            )
        )
    return edges


def operational_edges(
    nodes: dict[str, Kustomization],
    metrics_targets: dict[str, set[str]],
) -> list[Edge]:
    combined = component_edges(nodes) + metrics_edges(metrics_targets)
    deduped: dict[tuple[str, str, str], Edge] = {}
    for edge in combined:
        deduped[edge.key()] = edge
    return list(deduped.values())


def reverse_counts(edges: Iterable[Edge]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for edge in edges:
        if edge.kind == "deploy":
            counts[edge.target] += 1
    return counts


def is_platform(node_id: str, dependents: Counter[str]) -> bool:
    return node_id in UPSTREAM_PLATFORMS or dependents[node_id] >= PLATFORM_MIN_DEPENDENTS


def collapse_domains(
    nodes: dict[str, Kustomization],
    deploy: list[Edge],
    platforms: set[str],
) -> tuple[list[dict], list[dict]]:
    domain_to_platforms: dict[str, set[str]] = defaultdict(set)
    domain_counts: Counter[str] = Counter()

    for ks in nodes.values():
        if ks.node_id in platforms:
            continue
        domain = ks.namespace
        domain_counts[domain] += 1
        for dep in ks.deploy_deps:
            if dep in platforms:
                domain_to_platforms[domain].add(dep)

    graph_nodes: list[dict] = []
    graph_edges: list[dict] = []

    for platform in sorted(platforms):
        graph_nodes.append(
            {
                "id": platform,
                "meta": {
                    "kind": "platform",
                    "namespace": platform.split("/", 1)[0],
                },
            }
        )

    for domain in sorted(domain_to_platforms):
        label = DOMAIN_LABELS.get(domain, domain.replace("-", " ").title())
        domain_id = f"domain/{domain}"
        graph_nodes.append(
            {
                "id": domain_id,
                "meta": {
                    "kind": "domain",
                    "label": label,
                    "workloads": domain_counts[domain],
                },
            }
        )
        for platform in sorted(domain_to_platforms[domain]):
            graph_edges.append({"from": domain_id, "to": platform, "kind": "deploy"})

    return graph_nodes, graph_edges


def stacktower_graph(
    nodes: list[dict],
    edges: list[dict],
    *,
    edge_kind: str | None = None,
) -> dict:
    filtered_edges = edges
    if edge_kind is not None:
        filtered_edges = [edge for edge in edges if edge.get("kind", "deploy") == edge_kind]

    payload_edges = [{"from": edge["from"], "to": edge["to"]} for edge in filtered_edges]
    node_ids = {edge["from"] for edge in payload_edges} | {edge["to"] for edge in payload_edges}
    payload_nodes = [node for node in nodes if node["id"] in node_ids]

    for node in payload_nodes:
        node.setdefault("meta", {})
    return {"nodes": payload_nodes, "edges": payload_edges}


def load_tier_config(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as handle:
        return yaml.safe_load(handle) or {}


def node_matches(match: dict, node_id: str, namespace: str) -> bool:
    if node_id in match.get("exclude_nodes", []):
        return False
    if node_id in match.get("nodes", []):
        return True
    return namespace in match.get("namespaces", [])


def assign_partition(node_id: str, namespace: str, config: dict) -> tuple[str, str, str]:
    default = (WORKLOAD_GROUP, "workloads", "applications")
    for partition in config.get("partitions", []):
        if partition.get("default"):
            group = partition.get("group", partition.get("layer", WORKLOAD_GROUP))
            default = (group, partition["id"], partition.get("label", partition["id"]))
            continue
        if node_matches(partition.get("match", {}), node_id, namespace):
            group = partition.get("group", partition.get("layer", WORKLOAD_GROUP))
            return group, partition["id"], partition.get("label", partition["id"])
    return default


def vertical_tier_definitions(config: dict) -> list[tuple[int, dict]]:
    raw = config.get("vertical_tiers", {})
    if raw:
        return sorted(((int(key), meta or {}) for key, meta in raw.items()), key=lambda item: item[0])
    # Legacy fallback from layers.order
    layers = config.get("layers", {})
    return sorted(
        ((meta.get("order", index), {"label": meta.get("label", name), "groups": [name]}) for index, (name, meta) in enumerate(layers.items())),
        key=lambda item: item[0],
    )


def groups_for_vertical_tier(config: dict, vertical_tier: int) -> list[str]:
    for tier_num, meta in vertical_tier_definitions(config):
        if tier_num == vertical_tier:
            return meta.get("groups", [])
    return []


def group_definitions(config: dict) -> dict[str, dict]:
    groups = dict(config.get("groups", {}))
    if groups:
        return groups
    return dict(config.get("layers", {}))


def workload_group_name(config: dict) -> str:
    for name, meta in group_definitions(config).items():
        if meta and meta.get("collapse_by_namespace"):
            return name
    return WORKLOAD_GROUP


def vertical_tier_for_group(config: dict, group: str) -> int:
    for tier_num, meta in vertical_tier_definitions(config):
        if group in meta.get("groups", []):
            return tier_num
    group_meta = group_definitions(config).get(group, {})
    return int(group_meta.get("vertical_tier", group_meta.get("order", 999)))


def always_show_nodes(config: dict) -> set[str]:
    return set(config.get("always_show", []))


def should_show_explicit(
    node_id: str,
    group: str,
    dependents: Counter[str],
    config: dict,
    platforms: set[str],
) -> bool:
    if group == workload_group_name(config):
        return False
    if node_id in always_show_nodes(config):
        return True
    if node_id in platforms:
        return True
    return False


def diagram_node_id(
    node_id: str,
    nodes: dict[str, Kustomization],
    config: dict,
    dependents: Counter[str],
    platforms: set[str],
) -> str | None:
    ks = nodes[node_id]
    group, _, _ = assign_partition(node_id, ks.namespace, config)
    if group == workload_group_name(config):
        return mermaid_slug(f"workloads_{ks.namespace}")
    if should_show_explicit(node_id, group, dependents, config, platforms):
        return mermaid_slug(node_id.split("/")[-1])
    return None


def diagram_node_label(diagram_id: str, nodes: dict[str, Kustomization], node_ids: list[str]) -> str:
    if diagram_id.startswith("workloads_"):
        namespace = diagram_id.removeprefix("workloads_").replace("_", "-")
        count = sum(1 for node_id in node_ids if nodes[node_id].namespace == namespace)
        label = DOMAIN_LABELS.get(namespace, namespace.replace("-", " ").title())
        return f"{label}<br/>({count} ks)"
    return diagram_id.replace("_", "-")


def mermaid_slug(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", label.replace("-", "_").replace("/", "_"))
    if not slug:
        slug = "node"
    if slug[0].isdigit():
        slug = f"n_{slug}"
    return slug


def generate_mermaid_layers(
    nodes: dict[str, Kustomization],
    deploy: list[Edge],
    config: dict,
    dependents: Counter[str],
    platforms: set[str],
) -> str:
    visible: dict[str, str] = {}
    visible_sources: dict[str, list[str]] = defaultdict(list)

    for node_id, ks in nodes.items():
        diagram_id = diagram_node_id(node_id, nodes, config, dependents, platforms)
        if diagram_id is None:
            continue
        visible[node_id] = diagram_id
        visible_sources[diagram_id].append(node_id)

    node_meta: dict[str, tuple[str, str, str]] = {}
    for diagram_id, source_ids in visible_sources.items():
        source_id = source_ids[0]
        group, partition_id, partition_label = assign_partition(
            source_id,
            nodes[source_id].namespace,
            config,
        )
        if diagram_id.startswith("workloads_"):
            group = workload_group_name(config)
            partition_id = "workloads"
            partition_label = "applications"
        node_meta[diagram_id] = (group, partition_id, partition_label)

    grouped: dict[int, dict[str, dict[str, list[str]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for diagram_id, (group, partition_id, _) in node_meta.items():
        vertical_tier = vertical_tier_for_group(config, group)
        grouped[vertical_tier][group][partition_id].append(diagram_id)

    edge_set: set[tuple[str, str]] = set()
    for edge in deploy:
        source = visible.get(edge.source)
        target = visible.get(edge.target)
        if source and target and source != target:
            edge_set.add((source, target))

    lines = ["flowchart BT", ""]
    partition_labels = {
        partition["id"]: partition.get("label", partition["id"])
        for partition in config.get("partitions", [])
    }
    group_meta = group_definitions(config)

    for vertical_tier, vt_meta in vertical_tier_definitions(config):
        tier_groups = grouped.get(vertical_tier)
        if not tier_groups:
            continue

        vt_label = vt_meta.get("label", f"Tier {vertical_tier}")
        vt_desc = vt_meta.get("description", "")
        vt_title = f"{vt_label} — {vt_desc}" if vt_desc else vt_label
        vt_slug = mermaid_slug(f"vt_{vertical_tier}")
        lines.append(f'  subgraph {vt_slug}["{vt_title}"]')

        for group_name in groups_for_vertical_tier(config, vertical_tier):
            partitions = tier_groups.get(group_name)
            if not partitions:
                continue

            g_meta = group_meta.get(group_name, {})
            g_label = g_meta.get("label", group_name.title())
            g_desc = g_meta.get("description", "")
            g_title = f"{g_label} — {g_desc}" if g_desc else g_label
            g_slug = mermaid_slug(f"g_{group_name}")
            lines.append(f'    subgraph {g_slug}["{g_title}"]')

            for partition_id in sorted(partitions, key=lambda pid: partition_labels.get(pid, pid)):
                partition_label = partition_labels.get(partition_id, partition_id)
                p_slug = mermaid_slug(f"p_{group_name}_{partition_id}")
                lines.append(f'      subgraph {p_slug}["{partition_label}"]')

                for diagram_id in sorted(partitions[partition_id]):
                    node_label = diagram_node_label(diagram_id, nodes, visible_sources[diagram_id])
                    lines.append(f"        {diagram_id}[\"{node_label}\"]")

                lines.append("      end")

            lines.append("    end")

        lines.append("  end")
        lines.append("")

    for source, target in sorted(edge_set):
        lines.append(f"  {source} --> {target}")

    return "\n".join(lines).strip() + "\n"


def generate_mermaid_tiers(
    nodes: dict[str, Kustomization],
    _tiers: dict[str, int],
    deploy: list[Edge],
    dependents: Counter[str],
    platforms: set[str],
    config: dict,
) -> str:
    return generate_mermaid_layers(nodes, deploy, config, dependents, platforms)


def render_markdown(
    nodes: dict[str, Kustomization],
    tiers: dict[str, int],
    deploy: list[Edge],
    operational: list[Edge],
    metrics_targets: dict[str, set[str]],
    platforms: set[str],
    out_dir: Path,
    mermaid_tiers: str,
    layer_config: dict,
) -> str:
    dependents = reverse_counts(deploy)
    by_group: dict[str, list[str]] = defaultdict(list)
    for node_id in nodes:
        group, _, _ = assign_partition(node_id, nodes[node_id].namespace, layer_config)
        by_group[group].append(node_id)

    group_meta = group_definitions(layer_config)

    lines = [
        "# Cluster Platform Architecture",
        "",
        "Generated from Flux `Kustomization.spec.dependsOn`, declared Kustomize components,",
        "and Helm/manifest monitoring configuration (ServiceMonitor, PodMonitor, VMServiceScrape).",
        "Deploy edges define reconcile ordering; operational edges are separate edge kinds.",
        "",
        "## Architecture model",
        "",
        "The diagram uses **vertical tiers** (chart position) and **groups** (conceptual class).",
        "Platform and observability share a tier; data and AI share a tier — each remains a",
        "distinct group. Customize in [`tier-categories.yaml`](tier-categories.yaml).",
        "",
        "| Vertical tier | Groups | Role |",
        "| --- | --- | --- |",
        "| Substrate | Substrate | Cluster cannot run without (Cilium, cluster-meta) |",
        "| Infrastructure | Platform · Observability | Infra providers vs metrics/logs/checks |",
        "| Shared services | Data · AI | Shared Postgres/Redis and inference (Ollama) |",
        "| Workloads | Workloads | User-facing apps (media, downloads, games, …) |",
        "",
        "```mermaid",
        mermaid_tiers.rstrip(),
        "```",
        "",
        "## Load-bearing view (Stacktower)",
        "",
        "Stacktower emphasizes fan-out and load-bearing platforms; the Mermaid chart above",
        "emphasizes vertical tiers and logical groups. Use both: Mermaid for architecture",
        "storytelling, Stacktower for dependency density and DR prioritization stats.",
        "",
        "![Platform deploy tiers — app domains resting on shared platforms](platform-deploy.svg)",
        "",
        "Regenerate with `task architecture:diagram` (requires [Stacktower](https://github.com/stacktower-io/stacktower)).",
        "",
        "## Load-bearing platforms",
        "",
        "| Platform | Direct dependents | Group | dependsOn depth |",
        "| --- | ---: | --- | ---: |",
    ]

    for node_id, count in dependents.most_common():
        if not is_platform(node_id, dependents):
            continue
        group, _, _ = assign_partition(node_id, nodes[node_id].namespace, layer_config)
        group_label = group_meta.get(group, {}).get("label", group)
        lines.append(f"| `{node_id}` | {count} | {group_label} | {tiers.get(node_id, 0)} |")

    lines.extend(
        [
            "",
            "## Kustomizations by group",
            "",
        ]
    )

    for _vt, vt_meta in vertical_tier_definitions(layer_config):
        lines.append(f"### Vertical tier: {vt_meta.get('label', '')}")
        lines.append("")
        for group_name in vt_meta.get("groups", []):
            members = sorted(by_group.get(group_name, []))
            if not members:
                continue
            g_label = group_meta.get(group_name, {}).get("label", group_name.title())
            lines.append(f"**{g_label}**")
            lines.append("")
            if group_name == workload_group_name(layer_config):
                counts = Counter(nodes[node_id].namespace for node_id in members)
                for namespace, count in sorted(counts.items()):
                    label = DOMAIN_LABELS.get(namespace, namespace)
                    lines.append(f"- {label}: {count} Kustomizations")
            else:
                for node_id in members:
                    suffix = f" ({dependents[node_id]} dependents)" if dependents[node_id] else ""
                    lines.append(f"- `{node_id}`{suffix}")
            lines.append("")

    lines.extend(
        [
            "",
            "## Flux dependsOn depth",
            "",
            "Longest-path depth from `dependsOn` — useful for reconcile ordering, distinct from group assignment.",
            "",
        ]
    )

    by_tier: dict[int, list[str]] = defaultdict(list)
    for node_id, tier in tiers.items():
        by_tier[tier].append(node_id)

    for tier in sorted(by_tier):
        platform_nodes = [
            node_id
            for node_id in sorted(by_tier[tier])
            if is_platform(node_id, dependents) or dependents[node_id]
        ]
        if not platform_nodes:
            continue
        lines.append(f"### Depth {tier}")
        lines.append("")
        for node_id in platform_nodes:
            suffix = f" ({dependents[node_id]} dependents)" if dependents[node_id] else ""
            lines.append(f"- `{node_id}`{suffix}")
        lines.append("")

    monitor_counts = Counter(edge.target for edge in operational if edge.kind == "monitor")
    if monitor_counts:
        lines.extend(
            [
                "## Synthetic monitoring (Gatus component)",
                "",
                "These workloads expose HTTP checks via the shared Gatus component.",
                "Edge direction: `observability/gatus` → workload.",
                "",
            ]
        )
        for node_id, _ in monitor_counts.most_common():
            lines.append(f"- `{node_id}`")
        lines.append("")

    if metrics_targets:
        lines.extend(
            [
                "## Metrics scraping (Prometheus / Victoria Metrics)",
                "",
                "Detected from Helm chart values (`serviceMonitor`, `podMonitor`, `monitoring.enabled`)",
                "and raw Victoria Metrics scrape CRs in Git. These are first-class cluster relationships",
                "even when the chart renders the monitor object instead of a checked-in manifest.",
                "",
                "Edge direction: `observability/victoria-metrics-operator` → workload.",
                "",
            ]
        )
        for node_id in sorted(metrics_targets):
            signals = ", ".join(sorted(metrics_targets[node_id]))
            lines.append(f"- `{node_id}` ({signals})")
        lines.append("")

    metrics_count = sum(1 for edge in operational if edge.kind == "metrics")
    backup_count = sum(1 for edge in operational if edge.kind == "backup")
    scale_count = sum(1 for edge in operational if edge.kind == "scale")
    lines.extend(
        [
            "## Operational edge summary",
            "",
            f"- `metrics`: {metrics_count}",
            f"- `monitor`: {len(monitor_counts)}",
            f"- `backup`: {backup_count}",
            f"- `scale`: {scale_count}",
            "",
        ]
    )

    lines.extend(
        [
            "## Artifacts",
            "",
            "- `platform-deploy.svg` — Stacktower load-bearing view (committed)",
            "- `platform-tiers.mmd` — Mermaid layer model source (committed; also embedded above)",
            "- `tier-categories.yaml` — vertical tiers, groups, and partition rules",
            "- `platform-deploy.json`, `platform-operational.json`, `full-deploy.json` — generated locally by `task architecture:graph` (gitignored)",
            "",
            "```bash",
            "task architecture:diagram",
            "stacktower stats docs/architecture/platform-deploy.json",
            "```",
            "",
        ]
    )

    return "\n".join(lines)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root")
    parser.add_argument("--pattern", default=DEFAULT_KS_GLOB, help="Glob for ks.yaml files")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="Output directory")
    parser.add_argument(
        "--layer-config",
        type=Path,
        default=LAYER_CONFIG_PATH,
        help="Layer and partition config for Mermaid output",
    )
    args = parser.parse_args()

    layer_config = load_tier_config(args.layer_config)
    nodes = load_kustomizations(args.root, args.pattern)
    tiers = compute_tiers(nodes)
    deploy = deploy_edges(nodes)
    metrics_targets = discover_metrics_targets(args.root, nodes)
    operational = operational_edges(nodes, metrics_targets)
    dependents = reverse_counts(deploy)
    platforms = {node_id for node_id in nodes if is_platform(node_id, dependents)}
    mermaid_tiers = generate_mermaid_tiers(nodes, tiers, deploy, dependents, platforms, layer_config)

    collapsed_nodes, collapsed_edges = collapse_domains(nodes, deploy, platforms)
    collapsed_with_meta = [
        {
            **node,
            "meta": {
                **node.get("meta", {}),
                "tier": tiers.get(node["id"], 0),
                "dependents": dependents.get(node["id"], 0),
            },
        }
        if node["id"] in platforms
        else node
        for node in collapsed_nodes
    ]

    out_dir = args.out_dir
    (out_dir / "platform-tiers.mmd").write_text(mermaid_tiers)
    write_json(
        out_dir / "platform-deploy.json",
        stacktower_graph(collapsed_with_meta, collapsed_edges),
    )
    write_json(
        out_dir / "platform-operational.json",
        stacktower_graph(
            [{"id": node.node_id, "meta": {"kind": "workload", "namespace": node.namespace}} for node in nodes.values()]
            + [{"id": platform, "meta": {"kind": "platform"}} for platform in sorted(platforms)],
            [{"from": edge.source, "to": edge.target, "kind": edge.kind} for edge in operational],
        ),
    )
    write_json(
        out_dir / "full-deploy.json",
        stacktower_graph(
            [
                {
                    "id": node.node_id,
                    "meta": {
                        "kind": "platform" if node.node_id in platforms else "workload",
                        "namespace": node.namespace,
                        "tier": tiers[node.node_id],
                        "dependents": dependents.get(node.node_id, 0),
                    },
                }
                for node in nodes.values()
            ],
            [{"from": edge.source, "to": edge.target, "kind": edge.kind} for edge in deploy],
        ),
    )
    (out_dir / "README.md").write_text(
        render_markdown(
            nodes,
            tiers,
            deploy,
            operational,
            metrics_targets,
            platforms,
            out_dir,
            mermaid_tiers,
            layer_config,
        )
    )

    print(f"Wrote architecture artifacts to {out_dir}")
    print(f"  Kustomizations: {len(nodes)}")
    print(f"  Deploy edges: {len(deploy)}")
    print(f"  Operational edges: {len(operational)}")
    print(f"  Metrics targets: {len(metrics_targets)}")
    print(f"  Platform nodes: {len(platforms)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
