from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


ApplyStatus = Literal["added", "error"]


@dataclass
class AppliedChange:
    video_id: str
    title: str
    playlist: str
    status: ApplyStatus
    applied_at: datetime
    error: str | None = None
    wl_removed: bool = False


@dataclass
class AppliedLog:
    run_id: str
    applied_at: datetime
    total_moved: int
    changes: list[AppliedChange] = field(default_factory=list)
