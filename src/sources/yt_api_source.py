import structlog

from domain.video import Video
from youtube.client import YouTubeClient


log = structlog.get_logger()

_BLOCKED_WARNING = """
The YouTube Data API v3 does not allow reading the Watch Later playlist.
Google intentionally restricts this endpoint (HTTP 403/404).

Use one of the working sources instead:

  --from-file   Export Watch Later from takeout.google.com → playlists → CSV
  --from-yt-dlp (not yet implemented) yt-dlp with browser cookies

The --from-yt-api flag is kept for the day Google re-enables this endpoint.
"""


class YouTubeAPISource:
    """Fetch Watch Later via the YouTube Data API v3.

    Currently blocked by Google. The playlist endpoint returns 403/404 for
    Watch Later regardless of OAuth scope. Kept as a flag so it can be
    activated the moment Google re-enables access without changing the CLI.
    """

    def __init__(self, client: YouTubeClient) -> None:
        self._client = client

    @property
    def source_name(self) -> str:
        return "youtube-api"

    def fetch(self) -> list[Video]:
        log.warning("Attempting Watch Later via YouTube Data API v3 (known to be blocked by Google)")
        videos = self._client.get_watch_later_videos()

        if not videos:
            raise RuntimeError(_BLOCKED_WARNING.strip())

        return videos
