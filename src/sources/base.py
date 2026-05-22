from typing import Protocol

from domain.video import Video


class VideoSource(Protocol):
    """Fetch Watch Later videos from any backend.

    Implementations return Video objects with whatever fields they can provide.
    The caller is responsible for enrichment (tags, missing titles, etc.) via
    the YouTube API after fetch() returns.
    """

    @property
    def source_name(self) -> str:
        """Human-readable identifier used in log messages."""
        ...

    def fetch(self) -> list[Video]:
        """Return the list of Watch Later videos.

        Raises:
            RuntimeError: if the source is unavailable or misconfigured.
            NotImplementedError: if the source is a future placeholder.
        """
        ...
