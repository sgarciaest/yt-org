import re
from urllib.parse import parse_qs, urlparse

import structlog
from googleapiclient.errors import HttpError

from domain.video import Video
from youtube.client import YouTubeClient


log = structlog.get_logger()


# YouTube playlist IDs start with a 2-character prefix and contain only
# letters, digits, underscores and hyphens. Length is not strictly fixed
# (typically 13–34 chars), so allow a generous range.
_PLAYLIST_ID_RE = re.compile(r"^(?:PL|LL|FL|UU|OL|RD)[A-Za-z0-9_-]{10,}$")


class CustomPlaylistSource:
    """Fetch videos from a user-owned YouTube playlist.

    Accepts either a raw playlist ID (e.g. `PLrAXt…`) or a full URL
    (e.g. `https://www.youtube.com/playlist?list=PLrAXt…`).
    """

    def __init__(self, playlist: str, client: YouTubeClient) -> None:
        self._playlist_id = _extract_playlist_id(playlist)
        self._client = client

    @property
    def source_name(self) -> str:
        return f"playlist:{self._playlist_id}"

    @property
    def playlist_id(self) -> str:
        return self._playlist_id

    def fetch(self) -> list[Video]:
        try:
            return self._client.get_playlist_videos(self._playlist_id)
        except HttpError as e:
            status = getattr(e.resp, "status", "?")
            raise RuntimeError(
                f"Could not read playlist {self._playlist_id!r} (HTTP {status}). "
                "Check that the playlist exists and is owned by the authenticated account."
            ) from e


def _extract_playlist_id(value: str) -> str:
    raw = value.strip()
    if not raw:
        raise RuntimeError("Empty playlist identifier.")

    # URL form: pull out the `list` query parameter.
    if "://" in raw or raw.startswith("www."):
        parsed = urlparse(raw if "://" in raw else f"https://{raw}")
        list_values = parse_qs(parsed.query).get("list", [])
        if not list_values:
            raise RuntimeError(
                f"URL {raw!r} does not contain a `list=` query parameter."
            )
        raw = list_values[0]

    if not _PLAYLIST_ID_RE.match(raw):
        raise RuntimeError(
            f"{raw!r} does not look like a YouTube playlist ID "
            "(expected something like 'PLrAXt…' or a playlist URL)."
        )
    return raw
