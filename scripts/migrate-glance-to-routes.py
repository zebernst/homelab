#!/usr/bin/env python3
"""Move glance display annotations from workloads to primary HTTPRoutes."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs/architecture/glance-annotations.yaml"

DISPLAY_KEYS = ("glance/name", "glance/icon", "glance/category", "glance/url")
WORKLOAD_GLANCE_KEYS = ("glance/id", "glance/parent", "glance/hide")
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


def workload_lines(entry: dict) -> list[str]:
    indent = "          "
    lines: list[str] = []
    if entry.get("parent"):
        lines.append(f"{indent}glance/parent: {entry['parent']}")
    elif entry.get("id"):
        lines.append(f"{indent}glance/id: {entry['id']}")
    return lines


def strip_glance_from_controller(text: str, controller: str) -> str:
    controller_re = re.compile(
        rf"(^      {re.escape(controller)}:\n(?:        .+\n|\n)*?)(        annotations:\n(?:          .+\n)*)",
        re.MULTILINE,
    )

    def repl(match: re.Match[str]) -> str:
        prefix, ann_block = match.group(1), match.group(2)
        kept = []
        for line in ann_block.splitlines(keepends=True):
            if any(key in line for key in DISPLAY_KEYS + WORKLOAD_GLANCE_KEYS):
                continue
            kept.append(line)
        if not kept or kept == ["        annotations:\n"]:
            return prefix
        return prefix + "".join(kept)

    return controller_re.sub(repl, text, count=1)


def ensure_controller_workload_annotations(text: str, controller: str, lines: list[str]) -> str:
    if not lines:
        return text

    controller_re = re.compile(rf"^      {re.escape(controller)}:\n", re.MULTILINE)
    match = controller_re.search(text)
    if not match:
        print(f"WARN: controller {controller} not found", file=sys.stderr)
        return text

    after = text[match.end() :]
    ann_match = re.search(r"^        annotations:\n((?:          .+\n)*)", after, re.MULTILINE)
    if ann_match:
        insert_at = match.end() + ann_match.end(1)
        block = "".join(line + "\n" for line in lines)
        return text[:insert_at] + block + text[insert_at:]

    child_match = re.search(
        r"^        (?:(?:replicas|strategy|initContainers|containers|type|serviceAccount):)",
        after,
        re.MULTILINE,
    )
    insert_at = match.end() + (child_match.start() if child_match else 0)
    block = "        annotations:\n" + "".join(line + "\n" for line in lines)
    return text[:insert_at] + block + text[insert_at:]


def ensure_route_display_annotations(text: str, route: str, lines: list[str]) -> str:
    if not lines:
        return text

    route_re = re.compile(rf"^      {re.escape(route)}:\n", re.MULTILINE)
    route_start = text.find("    route:")
    if route_start == -1:
        return text
    route_block = text[route_start:]
    match = route_re.search(route_block)
    if not match:
        print(f"WARN: route {route} not found", file=sys.stderr)
        return text

    abs_start = route_start + match.start()
    after = route_block[match.end() :]
    ann_match = re.search(r"^        annotations:\n((?:          .+\n)*)", after, re.MULTILINE)
    if ann_match:
        insert_at = route_start + match.end() + ann_match.end(1)
        block = "".join(line + "\n" for line in lines)
        return text[:insert_at] + block + text[insert_at:]

    insert_at = route_start + match.end()
    block = "        annotations:\n" + "".join(line + "\n" for line in lines)
    return text[:insert_at] + block + text[insert_at:]


def strip_glance_from_route(text: str, route: str) -> str:
    route_start = text.find("    route:")
    if route_start == -1:
        return text
    route_block = text[route_start:]
    route_re = re.compile(
        rf"(^      {re.escape(route)}:\n(?:        .+\n)*?)(        annotations:\n(?:          .+\n)*)",
        re.MULTILINE,
    )

    def repl(match: re.Match[str]) -> str:
        prefix, ann_block = match.group(1), match.group(2)
        kept = []
        for line in ann_block.splitlines(keepends=True):
            if any(key in line for key in DISPLAY_KEYS):
                continue
            kept.append(line)
        if not kept or kept == ["        annotations:\n"]:
            return prefix.rstrip("\n") + "\n"
        return prefix + "".join(kept)

    updated = route_re.sub(repl, route_block, count=1)
    return text[:route_start] + updated


def should_include_url(entry: dict, text: str, route: str | None) -> bool:
    if not entry.get("url"):
        return False
    if entry.get("force_url"):
        return True
    rel = entry["file"].replace("\\", "/")
    if rel in MULTI_ROUTE_FILES:
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


def migrate_app_template(path: Path, entry: dict) -> bool:
    text = path.read_text()
    controller = entry["controller"]
    original = text

    text = strip_glance_from_controller(text, controller)
    for route_name in route_keys(text):
        text = strip_glance_from_route(text, route_name)

    text = ensure_controller_workload_annotations(text, controller, workload_lines(entry))

    if entry.get("parent"):
        pass
    elif entry.get("workload_only"):
        include_url = should_include_url(entry, text, None)
        text = ensure_controller_workload_annotations(
            text, controller, display_lines(entry, include_url=include_url)
        )
    else:
        route = pick_route(text, entry)
        if route:
            include_url = should_include_url(entry, text, route)
            text = ensure_route_display_annotations(
                text, route, display_lines(entry, include_url=include_url)
            )
        else:
            include_url = should_include_url(entry, text, None)
            text = ensure_controller_workload_annotations(
                text, controller, display_lines(entry, include_url=include_url)
            )

    if text != original:
        path.write_text(text)
        return True
    return False


def migrate_hide(path: Path, entry: dict) -> bool:
    text = path.read_text()
    controller = entry["controller"]
    original = text

    text = strip_glance_from_controller(text, controller)
    for route in route_keys(text):
        text = strip_glance_from_route(text, route)

    hide_line = '          glance/hide: "true"'
    text = ensure_controller_workload_annotations(text, controller, [hide_line])

    if text != original:
        path.write_text(text)
        return True
    return False


MULTI_ROUTE_FILES: set[str] = set()


def main() -> int:
    catalog = yaml.safe_load(CATALOG.read_text())
    MULTI_ROUTE_FILES.update(
        f"kubernetes/apps/{item.replace('/', '/app/')}/helmrelease.yaml" if "/" in item else item
        for item in catalog.get("multi_route", [])
    )
    # normalize multi_route paths
    MULTI_ROUTE_FILES.clear()
    for item in catalog.get("multi_route", []):
        ns, app = item.split("/", 1)
        if ns == "games" and app.startswith("minecraft/"):
            MULTI_ROUTE_FILES.add(f"kubernetes/apps/{ns}/{app.split('/', 1)[1]}/app/helmrelease.yaml")
        else:
            MULTI_ROUTE_FILES.add(f"kubernetes/apps/{ns}/{app}/app/helmrelease.yaml")

    changed = 0
    for entry in catalog.get("app_template", []):
        path = ROOT / entry["file"]
        if migrate_app_template(path, entry):
            changed += 1
            print(f"migrated {path}")

    for entry in catalog.get("hide", []):
        path = ROOT / entry["file"]
        if migrate_hide(path, entry):
            changed += 1
            print(f"hide {path}")

    print(f"Done. {changed} files migrated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
