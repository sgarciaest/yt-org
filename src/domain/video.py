from dataclasses import dataclass, field


@dataclass
class Video:
    video_id: str
    title: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    channel_name: str = ""
    category_id: str | None = None
    playlist_item_id: str | None = None
