from datetime import date
from pathlib import Path

import yaml


def load_channel_map(path: Path) -> dict[str, dict]:
    """Load the raw channel map (preserving all metadata including nulls)."""
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data.get("channel_topics", {})


def save_channel_map(channel_map: dict[str, dict], path: Path) -> None:
    """Write channel map to YAML, sorted alphabetically by channel name."""
    sorted_map = dict(sorted(channel_map.items(), key=lambda x: x[0].lower()))
    data = {"channel_topics": sorted_map}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def merge_channels(
    existing: dict[str, dict],
    new_names: set[str],
    today: date | None = None,
) -> tuple[dict[str, dict], int]:
    """Add channels from *new_names* that are not yet in *existing*.

    Returns (merged_map, count_of_new_entries).
    Existing entries (including their topic assignment) are never modified.
    """
    today = today or date.today()
    merged = dict(existing)
    added = 0
    for name in new_names:
        if name not in merged:
            merged[name] = {
                "topic": None,
                "added_at": today.isoformat(),
            }
            added += 1
    return merged, added
