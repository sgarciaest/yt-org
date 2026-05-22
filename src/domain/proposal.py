from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


Action = Literal["move", "review", "keep"]


@dataclass
class VideoProposal:
    video_id: str
    title: str
    predicted_topic: str | None
    confidence: float
    alternatives: dict[str, float]
    action: Action
    channel_name: str = ""
    description: str = ""
    tags: list[str] = field(default_factory=list)
    # Set when channel mapping is active. None means no mapping was found.
    channel_match: str | None = None
    # AI-only score before channel boost. None when no channel mapper is loaded.
    ai_confidence: float | None = None
    playlist_item_id: str | None = None


@dataclass
class Proposal:
    generated_at: datetime
    move_threshold: float
    review_threshold: float
    videos: list[VideoProposal] = field(default_factory=list)
