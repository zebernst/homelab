#!/usr/bin/env python3
"""Apply glance/* annotations from docs/architecture/glance-annotations.yaml."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/architecture/glance-annotations.yaml"


def glance_lines(entry: dict, *, hide: bool = False) -> list[str]:
    indent = "          "
    if hide:
        return [f'{indent}glance/hide: "true"']

    lines = [
        f"{indent}glance/id: {entry['id']}",
        f"{indent}glance/name: {entry['name']}",
        f"{indent}glance/icon: {entry['icon']}",
        f"{indent}glance/category: {entry['category']}",
    ]
    if entry.get("url"):
        lines.append(f'{indent}glance/url: {entry["url"]}')
    if entry.get("parent"):
        lines.append(f"{indent}glance/parent: {entry['parent']}")
    return lines


def already_has_glance(text: str) -> bool:
    return "glance/id:" in text or 'glance/hide: "true"' in text


def apply_app_template(path: Path, controller: str, lines: list[str]) -> bool:
    text = path.read_text()
    if already_has_glance(text):
        return False

    controller_re = re.compile(rf"^      {re.escape(controller)}:\n", re.MULTILINE)
    match = controller_re.search(text)
    if not match:
        print(f"WARN: controller {controller} not found in {path}", file=sys.stderr)
        return False

    after = text[match.end() :]
    ann_match = re.search(r"        annotations:\n((?:          .+\n)*)", after)
    if ann_match:
        insert_at = match.end() + ann_match.end(1)
        text = text[:insert_at] + "".join(line + "\n" for line in lines) + text[insert_at:]
        path.write_text(text)
        return True

    child_match = re.search(
        r"        (?:(?:replicas|strategy|initContainers|containers|type):)",
        after,
    )
    if not child_match:
        print(f"WARN: no insertion point for {controller} in {path}", file=sys.stderr)
        return False

    insert_at = match.end()
    ann_block = "        annotations:\n" + "".join(line + "\n" for line in lines)
    text = text[:insert_at] + ann_block + text[insert_at:]
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
        if apply_app_template(path, entry["controller"], glance_lines(entry)):
            updated += 1
            print(f"updated {path}")

    for entry in catalog.get("hide", []):
        path = ROOT / entry["file"]
        if apply_app_template(path, entry["controller"], glance_lines(entry, hide=True)):
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
