from collections.abc import Iterable
from typing import Any

DEFAULT_LIST_MERGE_KEYS = {
    "assumptions_to_test",
    "competitor_candidate_ids",
    "competitor_ids",
    "discovered_source_ids",
    "research_questions",
    "source_candidate_types",
}


def merge_metadata(
    base: dict[str, Any],
    extra: dict[str, Any] | None,
    *,
    list_merge_keys: set[str] | None = None,
) -> dict[str, Any]:
    """Merge JSON metadata while preserving stable order for list-like fields."""
    if not extra:
        return dict(base)

    merged = dict(base)
    merge_keys = DEFAULT_LIST_MERGE_KEYS | (list_merge_keys or set())
    for key, value in extra.items():
        if value is None:
            continue
        if key.endswith("_ids") or key in merge_keys:
            merged[key] = _stable_unique(
                _as_list(merged.get(key, [])),
                _as_list(value),
            )
        else:
            merged[key] = value
    return merged


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple | set):
        return list(value)
    return [value]


def _stable_unique(*groups: Iterable[Any]) -> list[Any]:
    ordered: list[Any] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            if item is None:
                continue
            marker = str(item)
            if marker not in seen:
                ordered.append(item)
                seen.add(marker)
    return ordered
