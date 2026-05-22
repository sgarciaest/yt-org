import csv
import json
from pathlib import Path

import yaml

from domain.video import Video


class FileSource:
    """Load Watch Later videos from a local file.

    Supported formats:
    - CSV  — Google Takeout export (columns: 'ID de vídeo' or 'Video ID')
    - YAML — list of video dicts, or {'videos': [...]}
    - JSON — same structure as YAML
    """

    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def source_name(self) -> str:
        return f"file:{self._path.name}"

    def fetch(self) -> list[Video]:
        if not self._path.exists():
            raise RuntimeError(f"File not found: {self._path}")

        if self._path.suffix == ".csv":
            return self._load_csv()
        return self._load_structured()

    def _load_csv(self) -> list[Video]:
        with self._path.open(encoding="utf-8", newline="") as f:
            lines = [l for l in f.readlines() if not l.lstrip().startswith("#")]

        videos: list[Video] = []
        for row in csv.DictReader(lines):
            # Google Takeout uses Spanish or English column names
            video_id = (
                row.get("Video ID")
                or row.get("video_id")
                or row.get("ID de vídeo")
                or row.get("ID de video")
                or ""
            ).strip()
            if video_id:
                videos.append(Video(video_id=video_id, title=""))
        return videos

    def _load_structured(self) -> list[Video]:
        with self._path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) if self._path.suffix in (".yaml", ".yml") else json.load(f)

        raw = data.get("videos", data) if isinstance(data, dict) else data
        return [
            Video(
                video_id=item.get("video_id", item.get("id", "")),
                title=item.get("title", ""),
                description=item.get("description", ""),
                tags=item.get("tags", []),
                channel_name=item.get("channel_name", item.get("channel", "")),
                category_id=item.get("category_id"),
            )
            for item in raw
        ]
