"""Data page identity: a path, plus the query when the query selects the document.

Per docs/ONBOARDING_SPEC.md § Data page identity.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from ...validation.har_utils import decode_body, path_from_url


def resources_of(candidates: list[dict[str, Any]]) -> list[tuple[dict[str, Any], str]]:
    """Pick one entry per resource from data page candidates, in HAR order."""
    by_path: dict[str, list[dict[str, Any]]] = {}
    for entry in candidates:
        by_path.setdefault(path_from_url(_url(entry)), []).append(entry)

    chosen: dict[int, str] = {}
    taken: set[str] = set()
    for path, group in by_path.items():
        documents: dict[frozenset[str], list[dict[str, Any]]] = {}
        others: list[dict[str, Any]] = []
        for entry in group:
            shape = _shape(entry)
            if shape is None:
                others.append(entry)
            else:
                documents.setdefault(shape, []).append(entry)

        if len(documents) < 2:
            picks = [(_largest(group), path)]
        else:
            picks = [(_largest(members), path + _selecting_query(members)) for members in documents.values()]
            if others:
                picks.append((_largest(others), path))
        for entry, resource in picks:
            if resource not in taken:
                taken.add(resource)
                chosen[id(entry)] = resource

    return [(entry, chosen[id(entry)]) for entry in candidates if id(entry) in chosen]


def _url(entry: dict[str, Any]) -> str:
    """The request URL of a HAR entry."""
    return str(entry.get("request", {}).get("url", ""))


def _largest(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """The entry with the longest body; the first of equals."""
    return max(entries, key=lambda e: len(e.get("response", {}).get("content", {}).get("text", "")))


def _shape(entry: dict[str, Any]) -> frozenset[str] | None:
    """Key paths of a JSON object or array body, ignoring values; None for any other body."""
    try:
        data = json.loads(decode_body(entry.get("response", {})))
    except ValueError:
        return None
    if not isinstance(data, (dict, list)):
        return None
    paths: set[str] = set()
    _collect_key_paths(data, "", paths)
    return frozenset(paths)


def _collect_key_paths(node: Any, prefix: str, paths: set[str]) -> None:
    """Add the dotted path of every key under ``node``; list items share one ``[]`` level."""
    if isinstance(node, dict):
        for key, value in node.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            paths.add(path)
            _collect_key_paths(value, path, paths)
    elif isinstance(node, list):
        for item in node:
            _collect_key_paths(item, f"{prefix}[]", paths)


def _selecting_query(members: list[dict[str, Any]]) -> str:
    """The query parameters every request for one document shares, as ``?a=1&b=2`` or ``""``."""
    segments = [[s for s in urlsplit(_url(entry)).query.split("&") if s] for entry in members]
    shared = [s for s in segments[0] if all(s in other for other in segments[1:])]
    return "?" + "&".join(shared) if shared else ""
