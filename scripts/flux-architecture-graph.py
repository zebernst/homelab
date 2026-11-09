#!/usr/bin/env python3
"""Generate a Mermaid architecture diagram from Flux Kustomization metadata."""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KS_GLOB = "kubernetes/**/ks.yaml"
DEFAULT_OUT_DIR = ROOT / "docs" / "architecture"
CONFIG_PATH = DEFAULT_OUT_DIR / "tier-categories.yaml"
WORKLOAD_GROUP = "workloads"
APPS_GLOB = "kubernetes/apps/**/*"

LOAD_BEARING_MIN_DEPENDENTS = 5

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

GROUP_STYLES = {
    "substrate": "fill:#1f2937,stroke:#9ca3af,color:#f9fafb",
    "platform": "fill:#1e3a5f,stroke:#60a5fa,color:#eff6ff",
    "observability": "fill:#312e81,stroke:#a78bfa,color:#f5f3ff",
    "data": "fill:#14532d,stroke:#4ade80,color:#f0fdf4",
    "ai": "fill:#581c87,stroke:#d8b4fe,color:#faf5ff",
    "workloads": "fill:#422006,stroke:#fbbf24,color:#fffbeb",
}
HUB_STYLE = "fill:none,stroke:none,color:transparent"


@dataclass
class Kustomization:
    node_id: str
    name: str
    namespace: str
    deploy_deps: set[str] = field(default_factory=set)


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
                ks = Kustomization(node_id=node_id, name=name, namespace=namespace)
                for dep in doc.get("spec", {}).get("dependsOn") or []:
                    dep_ns = dep.get("namespace", namespace)
                    ks.deploy_deps.add(f"{dep_ns}/{dep['name']}")
                nodes[node_id] = ks
    return nodes


def compute_depends_on_depth(nodes: dict[str, Kustomization]) -> dict[str, int]:
    memo: dict[str, int] = {}

    def depth(node_id: str, visiting: set[str] | None = None) -> int:
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
        value = 1 + max(depth(dep, visiting) for dep in ks.deploy_deps)
        visiting.remove(node_id)
        memo[node_id] = value
        return value

    for node_id in nodes:
        depth(node_id)
    return memo


def reverse_dependents(nodes: dict[str, Kustomization]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for ks in nodes.values():
        for dep in ks.deploy_deps:
            counts[dep] += 1
    return counts


def load_config(path: Path) -> dict:
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


def assign_partition(node_id: str, namespace: str, config: dict) -> tuple[str, str]:
    default = (WORKLOAD_GROUP, "workloads")
    for partition in config.get("partitions", []):
        if partition.get("default"):
            group = partition.get("group", WORKLOAD_GROUP)
            default = (group, partition["id"])
            continue
        if node_matches(partition.get("match", {}), node_id, namespace):
            return partition.get("group", WORKLOAD_GROUP), partition["id"]
    return default


def vertical_tier_definitions(config: dict) -> list[tuple[int, dict]]:
    raw = config.get("vertical_tiers", {})
    return sorted(((int(key), meta or {}) for key, meta in raw.items()), key=lambda item: item[0])


def groups_for_vertical_tier(config: dict, vertical_tier: int) -> list[str]:
    for tier_num, meta in vertical_tier_definitions(config):
        if tier_num == vertical_tier:
            return meta.get("groups", [])
    return []


def group_definitions(config: dict) -> dict[str, dict]:
    return dict(config.get("groups", {}))


def workload_group_name(config: dict) -> str:
    for name, meta in group_definitions(config).items():
        if meta.get("collapse_by_namespace"):
            return name
    return WORKLOAD_GROUP


def vertical_tier_for_group(config: dict, group: str) -> int:
    for tier_num, meta in vertical_tier_definitions(config):
        if group in meta.get("groups", []):
            return tier_num
    return 999


def always_show(config: dict) -> set[str]:
    return set(config.get("always_show", []))


def mermaid_id(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_]", "_", label.replace("-", "_").replace("/", "_"))
    if not slug:
        slug = "node"
    if slug[0].isdigit():
        slug = f"n_{slug}"
    return slug


def should_render(node_id: str, group: str, config: dict, dependents: Counter[str]) -> bool:
    if group == workload_group_name(config):
        return True
    if node_id in always_show(config):
        return True
    if dependents[node_id] >= LOAD_BEARING_MIN_DEPENDENTS:
        return True
    return False


def render_node_id(node_id: str, group: str, namespace: str, config: dict) -> str:
    if group == workload_group_name(config):
        return mermaid_id(f"wl_{namespace}")
    return mermaid_id(node_id.split("/")[-1])


def render_node_label(
    node_id: str,
    render_id: str,
    group: str,
    namespace: str,
    source_ids: list[str],
    nodes: dict[str, Kustomization],
    dependents: Counter[str],
) -> str:
    if render_id.startswith("wl_"):
        count = len(source_ids)
        label = DOMAIN_LABELS.get(namespace, namespace.replace("-", " ").title())
        return f"{label}<br/>({count} ks)"

    short = node_id.split("/")[-1]
    inbound = dependents.get(node_id, 0)
    if inbound >= LOAD_BEARING_MIN_DEPENDENTS:
        return f"{short}<br/>({inbound} deps)"
    return short


def partition_label(partition_id: str, config: dict) -> str:
    for partition in config.get("partitions", []):
        if partition["id"] == partition_id:
            return partition.get("label", partition_id.rsplit("/", 1)[-1])
    return partition_id.rsplit("/", 1)[-1]


def partition_sort_key(partition_id: str, config: dict) -> tuple[int, str]:
    for partition in config.get("partitions", []):
        if partition["id"] == partition_id:
            label = partition.get("label", partition_id.rsplit("/", 1)[-1])
            return partition.get("order", 999), label
    return 999, partition_id


def node_group(node_id: str, nodes: dict[str, Kustomization], config: dict) -> str:
    return assign_partition(node_id, nodes[node_id].namespace, config)[0]


def aggregate_tier_edges(nodes: dict[str, Kustomization], config: dict) -> set[tuple[int, int]]:
    """Summarize cross-tier Flux dependsOn as higher-tier -> lower-tier edges only."""
    edges: set[tuple[int, int]] = set()
    for ks in nodes.values():
        source_tier = vertical_tier_for_group(config, node_group(ks.node_id, nodes, config))
        for dep in ks.deploy_deps:
            if dep not in nodes:
                continue
            target_tier = vertical_tier_for_group(config, node_group(dep, nodes, config))
            if source_tier > target_tier:
                edges.add((source_tier, target_tier))
    return edges


def tier_hub_id(vertical_tier: int) -> str:
    return mermaid_id(f"hub_vt{vertical_tier}")


def generate_mermaid(
    nodes: dict[str, Kustomization],
    config: dict,
    dependents: Counter[str],
) -> str:
    rendered: dict[str, str] = {}
    rendered_sources: dict[str, list[str]] = defaultdict(list)

    for node_id, ks in nodes.items():
        group, _ = assign_partition(node_id, ks.namespace, config)
        if not should_render(node_id, group, config, dependents):
            continue
        render_id = render_node_id(node_id, group, ks.namespace, config)
        rendered[node_id] = render_id
        rendered_sources[render_id].append(node_id)

    placements: dict[int, dict[str, dict[str, list[str]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for render_id, source_ids in rendered_sources.items():
        sample = source_ids[0]
        group, partition_id = assign_partition(sample, nodes[sample].namespace, config)
        if render_id.startswith("wl_"):
            group = workload_group_name(config)
            partition_id = "workloads"
        vertical_tier = vertical_tier_for_group(config, group)
        placements[vertical_tier][group][partition_id].append(render_id)

    tier_edges = aggregate_tier_edges(nodes, config)
    active_tiers = set(placements.keys())

    lines = [
        "flowchart BT",
        "",
        "  %% Cross-tier dependsOn summary (higher tier -.-> lower tier it depends on)",
        "",
    ]

    group_meta = group_definitions(config)

    for vertical_tier, vt_meta in vertical_tier_definitions(config):
        tier_nodes = placements.get(vertical_tier)
        if not tier_nodes:
            continue

        vt_label = vt_meta.get("label", f"Tier {vertical_tier}")
        vt_desc = vt_meta.get("description", "")
        title = f"{vt_label} — {vt_desc}" if vt_desc else vt_label
        vt_id = mermaid_id(f"vt{vertical_tier}")
        lines.append(f'  subgraph {vt_id}["{title}"]')

        for group_name in groups_for_vertical_tier(config, vertical_tier):
            partitions = tier_nodes.get(group_name)
            if not partitions:
                continue

            meta = group_meta.get(group_name, {})
            g_label = meta.get("label", group_name.title())
            g_desc = meta.get("description")
            g_title = f"{g_label} — {g_desc}" if g_desc else g_label
            g_id = mermaid_id(f"g_{group_name}")
            lines.append(f'    subgraph {g_id}["{g_title}"]')

            partition_keys = sorted(partitions.keys(), key=lambda pid: partition_sort_key(pid, config))
            use_partition_subgraphs = len(partition_keys) > 1 or (
                len(partition_keys) == 1 and partition_keys[0] != "workloads"
            )

            for partition_id in partition_keys:
                render_ids = sorted(set(partitions[partition_id]))
                if use_partition_subgraphs:
                    p_id = mermaid_id(f"p_{group_name}_{partition_id}")
                    p_title = partition_label(partition_id, config)
                    lines.append(f'      subgraph {p_id}["{p_title}"]')
                    indent = "        "
                else:
                    indent = "      "

                for render_id in render_ids:
                    sample = rendered_sources[render_id][0]
                    ns = nodes[sample].namespace
                    group, _ = assign_partition(sample, ns, config)
                    label = render_node_label(
                        sample,
                        render_id,
                        group,
                        ns,
                        rendered_sources[render_id],
                        nodes,
                        dependents,
                    )
                    safe_label = label.replace('"', "'")
                    lines.append(f'{indent}{render_id}["{safe_label}"]')
                    lines.append(f"{indent}class {render_id} {group_name}")

                if use_partition_subgraphs:
                    lines.append("      end")

            lines.append("    end")

        tier_hub = tier_hub_id(vertical_tier)
        lines.append(f"    {tier_hub}(( ))")
        lines.append(f"    class {tier_hub} hub")
        lines.append("  end")
        lines.append("")

    for source_tier, target_tier in sorted(tier_edges):
        if source_tier not in active_tiers or target_tier not in active_tiers:
            continue
        lines.append(f"  {tier_hub_id(source_tier)} -.-> {tier_hub_id(target_tier)}")

    lines.extend(["", "  %% styling"])
    lines.append(f"  classDef hub {HUB_STYLE}")
    for group_name, style in GROUP_STYLES.items():
        lines.append(f"  classDef {group_name} {style}")

    return "\n".join(lines).strip() + "\n"


def render_readme(
    nodes: dict[str, Kustomization],
    depths: dict[str, int],
    dependents: Counter[str],
    config: dict,
    mermaid: str,
) -> str:
    by_group: dict[str, list[str]] = defaultdict(list)
    for node_id in nodes:
        group, _ = assign_partition(node_id, nodes[node_id].namespace, config)
        by_group[group].append(node_id)

    group_meta = group_definitions(config)
    lines = [
        "# Cluster Platform Architecture",
        "",
        "Generated from Flux `Kustomization.spec.dependsOn`. Customize vertical tiers, groups,",
        "and partitions in [`tier-categories.yaml`](tier-categories.yaml).",
        "",
        "| Vertical tier | Groups | Role |",
        "| --- | --- | --- |",
        "| Substrate | Substrate | Gitops, network, PKI, storage, hardware, meta |",
        "| Infrastructure | Platform · Observability | Infra providers vs metrics/logs/checks |",
        "| Shared services | Data · AI | Shared Postgres/Redis and inference |",
        "| Workloads | Workloads | User-facing applications |",
        "",
        "```mermaid",
        mermaid.rstrip(),
        "```",
        "",
        "Regenerate: `task architecture:graph`",
        "",
        "Dashed edges summarize cross-tier Flux `dependsOn` (higher tier depends on lower).",
        "Individual Kustomization edges are omitted to keep the diagram readable.",
        "",
        "## Load-bearing platforms",
        "",
        "Kustomizations with the most direct `dependsOn` inbound edges.",
        "",
        "| Kustomization | Dependents | Group | dependsOn depth |",
        "| --- | ---: | --- | ---: |",
    ]

    for node_id, count in dependents.most_common(15):
        group, _ = assign_partition(node_id, nodes[node_id].namespace, config)
        group_label = group_meta.get(group, {}).get("label", group)
        lines.append(f"| `{node_id}` | {count} | {group_label} | {depths.get(node_id, 0)} |")

    lines.extend(["", "## Kustomizations by group", ""])
    for _vt, vt_meta in vertical_tier_definitions(config):
        lines.append(f"### {vt_meta.get('label', '')}")
        lines.append("")
        for group_name in vt_meta.get("groups", []):
            members = sorted(by_group.get(group_name, []))
            if not members:
                continue
            g_label = group_meta.get(group_name, {}).get("label", group_name.title())
            lines.append(f"**{g_label}**")
            lines.append("")
            if group_name == workload_group_name(config):
                counts = Counter(nodes[n].namespace for n in members)
                for namespace, count in sorted(counts.items()):
                    label = DOMAIN_LABELS.get(namespace, namespace)
                    lines.append(f"- {label}: {count}")
            else:
                for node_id in members:
                    suffix = f" ({dependents[node_id]} deps)" if dependents[node_id] else ""
                    lines.append(f"- `{node_id}`{suffix}")
            lines.append("")

    lines.extend(
        [
            "## Artifacts",
            "",
            "- [`platform-tiers.mmd`](platform-tiers.mmd) — Mermaid source (also embedded above)",
            "- [`tier-categories.yaml`](tier-categories.yaml) — vertical tiers, groups, partitions",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--pattern", default=DEFAULT_KS_GLOB)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()

    config = load_config(args.config)
    nodes = load_kustomizations(args.root, args.pattern)
    depths = compute_depends_on_depth(nodes)
    dependents = reverse_dependents(nodes)
    mermaid = generate_mermaid(nodes, config, dependents)

    out_dir = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "platform-tiers.mmd").write_text(mermaid)
    (out_dir / "README.md").write_text(render_readme(nodes, depths, dependents, config, mermaid))

    print(f"Wrote architecture diagram to {out_dir}")
    print(f"  Kustomizations: {len(nodes)}")
    print(f"  Rendered nodes: {len({n for n, ks in nodes.items() if should_render(n, assign_partition(n, ks.namespace, config)[0], config, dependents)})}")
    print(f"  Deploy edges: {sum(len(ks.deploy_deps) for ks in nodes.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
