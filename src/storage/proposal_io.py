from datetime import datetime, timezone
from pathlib import Path

import yaml

from domain.proposal import Proposal, VideoProposal


def save_proposal(proposal: Proposal, path: str | Path) -> None:
    data = _to_dict(proposal)
    Path(path).write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )


def load_proposal(path: str | Path) -> Proposal:
    with Path(path).open(encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return _from_dict(data)


def _to_dict(proposal: Proposal) -> dict:
    return {
        "generated_at": proposal.generated_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        "thresholds": {
            "auto_move": proposal.move_threshold,
            "review": proposal.review_threshold,
        },
        "videos": [
            {
                "video_id": vp.video_id,
                "title": vp.title,
                "predicted_topic": vp.predicted_topic,
                "confidence": round(vp.confidence, 4),
                "alternatives": {k: round(v, 4) for k, v in vp.alternatives.items()},
                "action": vp.action,
                **({"playlist_item_id": vp.playlist_item_id} if vp.playlist_item_id else {}),
            }
            for vp in proposal.videos
        ],
    }


def _from_dict(data: dict) -> Proposal:
    thresholds = data.get("thresholds", {})
    videos = [
        VideoProposal(
            video_id=v["video_id"],
            title=v["title"],
            predicted_topic=v.get("predicted_topic"),
            confidence=float(v.get("confidence", 0.0)),
            alternatives=v.get("alternatives", {}),
            action=v.get("action", "keep"),
            playlist_item_id=v.get("playlist_item_id"),
        )
        for v in data.get("videos", [])
    ]
    return Proposal(
        generated_at=datetime.now(timezone.utc),
        move_threshold=float(thresholds.get("auto_move", 0.82)),
        review_threshold=float(thresholds.get("review", 0.60)),
        videos=videos,
    )
