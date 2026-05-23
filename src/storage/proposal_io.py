from datetime import datetime, timezone
from pathlib import Path

import yaml

from domain.proposal import Proposal, VideoProposal


# Maximum lengths for human-readable YAML output.
# The full strings are kept in memory for the classifier; only the YAML is truncated.
_TITLE_MAX = 120
_CHANNEL_MAX = 80
_DESCRIPTION_MAX = 300
_TAG_MAX = 50
_TAGS_MAX_COUNT = 8


_ACTION_MARKERS = {
    "move": "🔀",
    "review": "👀",
    "keep": "📌",
}


def save_proposal(proposal: Proposal, path: str | Path) -> None:
    data = _to_dict(proposal)
    content = yaml.dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False)
    for action, emoji in _ACTION_MARKERS.items():
        content = content.replace(f"action: {action}\n", f"action: {action}  # {emoji}\n")
    Path(path).write_text(content, encoding="utf-8")


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
        "videos": [_video_to_dict(vp) for vp in proposal.videos],
    }


def _video_to_dict(vp: VideoProposal) -> dict:
    # Source data block first so the human can read it before the classification block
    entry: dict = {
        "video_id": vp.video_id,
        "title": _clip(vp.title, _TITLE_MAX),
        "channel": _clip(vp.channel_name, _CHANNEL_MAX),
    }

    if vp.tags:
        clipped_tags = [_clip(t, _TAG_MAX) for t in vp.tags[:_TAGS_MAX_COUNT]]
        entry["tags"] = clipped_tags

    if vp.description:
        entry["description"] = _clip(vp.description, _DESCRIPTION_MAX)

    # Classification results block
    if vp.channel_match is not None:
        entry["channel_match"] = vp.channel_match
        entry["ai_confidence"] = round(vp.ai_confidence, 4) if vp.ai_confidence is not None else None

    entry["predicted_topic"] = vp.predicted_topic
    entry["confidence"] = round(vp.confidence, 4)
    entry["alternatives"] = {k: round(v, 4) for k, v in vp.alternatives.items()}
    entry["action"] = vp.action

    if vp.playlist_item_id:
        entry["playlist_item_id"] = vp.playlist_item_id

    return entry


def _from_dict(data: dict) -> Proposal:
    thresholds = data.get("thresholds", {})
    videos = [
        VideoProposal(
            video_id=v["video_id"],
            title=v.get("title", ""),
            predicted_topic=v.get("predicted_topic"),
            confidence=float(v.get("confidence", 0.0)),
            alternatives=v.get("alternatives", {}),
            action=v.get("action", "keep"),
            channel_name=v.get("channel", ""),
            description=v.get("description", ""),
            tags=v.get("tags", []),
            channel_match=v.get("channel_match"),
            ai_confidence=v.get("ai_confidence"),
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


def _clip(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."
