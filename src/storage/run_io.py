from pathlib import Path

import yaml

from domain.run import AppliedLog


def save_applied(applied: AppliedLog, path: Path) -> None:
    path.write_text(
        yaml.dump(_to_dict(applied), allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def append_history(applied: AppliedLog, history_path: Path) -> None:
    existing: list[dict] = []
    if history_path.exists():
        with history_path.open(encoding="utf-8") as f:
            existing = yaml.safe_load(f) or []
    existing.append(_to_dict(applied))
    history_path.write_text(
        yaml.dump(existing, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def _to_dict(applied: AppliedLog) -> dict:
    return {
        "run_id": applied.run_id,
        "applied_at": applied.applied_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "total_moved": applied.total_moved,
        "changes": [
            {
                "video_id": c.video_id,
                "title": c.title,
                "playlist": c.playlist,
                "status": c.status,
                "applied_at": c.applied_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
                **({"error": c.error} if c.error else {}),
            }
            for c in applied.changes
        ],
    }
