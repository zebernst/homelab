#!/usr/bin/env python3
"""Apply glance/* annotations from docs/architecture/glance-annotations.yaml."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/architecture/glance-annotations.yaml"
ROUTE_PRIORITY = ("app", "id", "plex", "external", "api", "cv")


def route_keys(text: str) -> list[str]:
    if "    route:" not in text:
        return []
    block = text.split("    route:", 1)[1]
    m = re.match(r"(.*?)(?=^    \w|\Z)", block, re.MULTILINE | re.DOTALL)
    if not m:
        return []
    return re.findall(r"^      (\S+):", m.group(1), re.MULTILINE)


def pick_route(text: str, entry: dict) -> str | None:
    if entry.get("route"):
        return entry["route"]
    keys = route_keys(text)
    if not keys:
        return None
    for key in ROUTE_PRIORITY:
        if key in keys:
            return key
    non_canonical = [k for k in keys if k != "canonical"]
    return non_canonical[0] if non_canonical else keys[0]


def display_lines(entry: dict, *, include_url: bool) -> list[str]:
    indent = "          "
    lines = [
        f"{indent}glance/name: {entry['name']}",
        f"{indent}glance/icon: {entry['icon']}",
        f"{indent}glance/category: {entry['category']}",
    ]
    if include_url and entry.get("url"):
        lines.append(f"{indent}glance/url: {entry['url']}")
    return lines


def workload_lines(entry: dict, *, hide: bool = False) -> list[str]:
    indent = "          "
    if hide:
        return [f'{indent}glance/hide: "true"']
    if entry.get("parent"):
        return [f"{indent}glance/parent: {entry['parent']}"]
    if entry.get("id"):
        return [f"{indent}glance/id: {entry['id']}"]
    return []


def already_has_glance(text: str) -> bool:
    return "glance/id:" in text or 'glance/hide: "true"' in text or "glance/parent:" in text


def controller_block_end(text: str, start: int) -> int:
    lines = text[start:].splitlines(keepends=True)
    consumed = 0
    for line in lines[1:]:
        if line.startswith("      ") and not line.startswith("        ") and line.strip():
            break
        if line.startswith("    ") and not line.startswith("      ") and line.strip():
            break
        consumed += len(line)
    return start + consumed


def merge_annotations(text: str, anchor_re: re.Pattern[str], lines: list[str]) -> str:
    match = anchor_re.search(text)
    if not match:
        return text
    block_end = controller_block_end(text, match.start()) if "      " in anchor_re.pattern else len(text)
    block = text[match.start() : block_end]
    ann_match = re.search(r"^        annotations:\n((?:          .+\n)*)", block, re.MULTILINE)
    if ann_match:
        insert_at = match.start() + ann_match.end(1)
        payload = "".join(line + "\n" for line in lines)
        return text[:insert_at] + payload + text[insert_at:]
    insert_at = match.end()
    payload = "        annotations:\n" + "".join(line + "\n" for line in lines)
    return text[:insert_at] + payload + text[insert_at:]


def should_include_url(entry: dict, text: str, route: str | None) -> bool:
    if not entry.get("url"):
        return False
    if entry.get("force_url"):
        return True
    if not route:
        return True
    host = entry["url"].split("://", 1)[-1].split("/", 1)[0]
    route_start = text.find("    route:")
    if route_start == -1:
        return True
    route_block = text[route_start:]
    route_section = re.search(
        rf"      {re.escape(route)}:(.*?)(?=^      \S|\Z)",
        route_block,
        re.DOTALL | re.MULTILINE,
    )
    if route_section and host in route_section.group(1):
        return False
    return True


def apply_app_template(path: Path, entry: dict, *, hide: bool = False) -> bool:
    text = path.read_text()
    if already_has_glance(text):
        return False

    controller = entry["controller"]
    controller_re = re.compile(rf"^      {re.escape(controller)}:\n", re.MULTILINE)
    if not controller_re.search(text):
        print(f"WARN: controller {controller} not found in {path}", file=sys.stderr)
        return False

    text = merge_annotations(text, controller_re, workload_lines(entry, hide=hide))

    if hide or entry.get("parent"):
        path.write_text(text)
        return True

    if entry.get("workload_only"):
        text = merge_annotations(
            text,
            controller_re,
            display_lines(entry, include_url=should_include_url(entry, text, None)),
        )
        path.write_text(text)
        return True

    route = pick_route(text, entry)
    if route:
        route_re = re.compile(rf"^      {re.escape(route)}:\n", re.MULTILINE)
        route_start = text.find("    route:")
        route_block = text[route_start:]
        if route_re.search(route_block):
            abs_route_re = re.compile(rf"(?m)^      {re.escape(route)}:\n")
            text = merge_annotations(
                text,
                abs_route_re,
                display_lines(entry, include_url=should_include_url(entry, text, route)),
            )
            path.write_text(text)
            return True

    text = merge_annotations(
        text,
        controller_re,
        display_lines(entry, include_url=should_include_url(entry, text, None)),
    )
    path.write_text(text)
    return True


def set_nested(values: dict, path: str, annotations: dict) -> None:
    parts = path.split(".")
    cur = values
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    key = parts[-1]
    cur.setdefault(key, {})
    cur[key].update(annotations)


def apply_upstream(path: Path, entry: dict) -> bool:
    documents = list(yaml.safe_load_all(path.read_text()))
    changed = False
    annotations = {
        "glance/id": entry["id"],
        "glance/name": entry["name"],
        "glance/icon": entry["icon"],
        "glance/category": entry["category"],
    }
    if entry.get("url"):
        annotations["glance/url"] = entry["url"]
    if entry.get("hide"):
        annotations = {"glance/hide": "true"}

    for doc in documents:
        if not isinstance(doc, dict) or doc.get("kind") != "HelmRelease":
            continue
        values = doc.setdefault("spec", {}).setdefault("values", {})
        if entry.get("hide"):
            set_nested(values, entry["values_path"], annotations)
            changed = True
            continue
        target = values
        for part in entry["values_path"].split("."):
            target = target.setdefault(part, {}) if isinstance(target, dict) else target
        if isinstance(target, dict):
            if target.get("glance/id"):
                continue
            target.update(annotations)
            changed = True

    if changed:
        path.write_text("---\n".join(yaml.dump(doc, sort_keys=False) for doc in documents))
    return changed


def main() -> int:
    catalog = yaml.safe_load(CATALOG.read_text())
    updated = 0

    for entry in catalog.get("app_template", []):
        path = ROOT / entry["file"]
        if apply_app_template(path, entry):
            updated += 1
            print(f"updated {path}")

    for entry in catalog.get("hide", []):
        path = ROOT / entry["file"]
        if apply_app_template(path, entry, hide=True):
            updated += 1
            print(f"hidden {path}")

    for entry in catalog.get("upstream_values", []):
        path = ROOT / entry["file"]
        if apply_upstream(path, entry):
            updated += 1
            print(f"upstream {path} ({entry['values_path']})")

    print(f"Done. {updated} files updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
