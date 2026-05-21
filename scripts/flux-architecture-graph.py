#!/usr/bin/env python3
"""Generate platform architecture graphs from Flux Kustomization dependsOn edges."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KS_GLOB = "kubernetes/**/ks.yaml"
DEFAULT_OUT_DIR = ROOT / "docs" / "architecture"

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


def render_markdown(
    nodes: dict[str, Kustomization],
    tiers: dict[str, int],
    deploy: list[Edge],
    operational: list[Edge],
    metrics_targets: dict[str, set[str]],
    platforms: set[str],
    out_dir: Path,
) -> str:
    dependents = reverse_counts(deploy)
    by_tier: dict[int, list[str]] = defaultdict(list)
    for node_id, tier in tiers.items():
        by_tier[tier].append(node_id)

    lines = [
        "# Cluster Platform Architecture",
        "",
        "Generated from Flux `Kustomization.spec.dependsOn`, declared Kustomize components,",
        "and Helm/manifest monitoring configuration (ServiceMonitor, PodMonitor, VMServiceScrape).",
        "Deploy edges define reconcile ordering; operational edges are separate edge kinds.",
        "",
        "## Load-bearing platforms",
        "",
        "| Platform | Direct dependents | Tier |",
        "| --- | ---: | ---: |",
    ]

    for node_id, count in dependents.most_common():
        if not is_platform(node_id, dependents):
            continue
        lines.append(f"| `{node_id}` | {count} | {tiers.get(node_id, 0)} |")

    lines.extend(
        [
            "",
            "## Deploy tiers",
            "",
            "Tier 0 sits at the bottom of the reconcile stack; higher tiers rest on lower ones.",
            "",
        ]
    )

    for tier in sorted(by_tier):
        platform_nodes = [
            node_id
            for node_id in sorted(by_tier[tier])
            if is_platform(node_id, dependents) or dependents[node_id]
        ]
        if not platform_nodes:
            continue
        lines.append(f"### Tier {tier}")
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
            f"- `{out_dir.name}/platform-deploy.json` — collapsed deploy graph for Stacktower",
            f"- `{out_dir.name}/platform-operational.json` — metrics/monitor/backup/scale edges",
            f"- `{out_dir.name}/full-deploy.json` — all Kustomizations and deploy edges",
            "",
            "```bash",
            "stacktower render docs/architecture/platform-deploy.json -o docs/architecture/platform-deploy.svg",
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
    args = parser.parse_args()

    nodes = load_kustomizations(args.root, args.pattern)
    tiers = compute_tiers(nodes)
    deploy = deploy_edges(nodes)
    metrics_targets = discover_metrics_targets(args.root, nodes)
    operational = operational_edges(nodes, metrics_targets)
    dependents = reverse_counts(deploy)
    platforms = {node_id for node_id in nodes if is_platform(node_id, dependents)}

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
        render_markdown(nodes, tiers, deploy, operational, metrics_targets, platforms, out_dir)
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
