import structlog
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential

from domain.video import Video


log = structlog.get_logger()


class YouTubeClient:
    def __init__(self, credentials: Credentials) -> None:
        self._yt = build("youtube", "v3", credentials=credentials)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def get_playlist_videos(self, playlist_id: str) -> list[Video]:
        """List all videos in a user-owned playlist."""
        videos: list[Video] = []
        next_page_token: str | None = None

        while True:
            response = (
                self._yt.playlistItems()
                .list(
                    part="snippet,contentDetails",
                    playlistId=playlist_id,
                    maxResults=50,
                    pageToken=next_page_token,
                )
                .execute()
            )

            for item in response.get("items", []):
                video = _parse_playlist_item(item)
                if video:
                    videos.append(video)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        log.info("Fetched videos from playlist", playlist_id=playlist_id, count=len(videos))
        return videos

    def enrich_videos(self, videos: list[Video]) -> list[Video]:
        """Fetch title, description, channel, tags and category for each video."""
        enriched: list[Video] = []
        total_found = 0

        for chunk in _chunks(videos, 50):
            ids = ",".join(v.video_id for v in chunk)
            try:
                response = (
                    self._yt.videos()
                    .list(part="snippet", id=ids)
                    .execute()
                )
            except HttpError as e:
                log.warning("Failed to enrich video batch", error=str(e))
                enriched.extend(chunk)
                continue

            # videos.list uses "channelTitle"; playlistItems.list uses "videoOwnerChannelTitle"
            details_by_id: dict[str, dict] = {
                item["id"]: item["snippet"]
                for item in response.get("items", [])
            }
            for video in chunk:
                details = details_by_id.get(video.video_id)
                if details:
                    video.title = details.get("title", video.title)
                    video.description = details.get("description", video.description)
                    video.channel_name = details.get("channelTitle", video.channel_name)
                    video.tags = details.get("tags", [])
                    video.category_id = details.get("categoryId")
                    total_found += 1
                else:
                    log.debug("Video not found in API response (private/deleted?)", video_id=video.video_id)
                enriched.append(video)

        missing = len(videos) - total_found
        log.info("Enriched videos", total=len(videos), found=total_found, missing=missing)
        if missing:
            log.warning("Some videos could not be enriched", missing=missing, reason="private, deleted, or region-blocked")
        return enriched


def _parse_playlist_item(item: dict) -> Video | None:
    snippet = item.get("snippet", {})
    video_id = snippet.get("resourceId", {}).get("videoId")
    if not video_id:
        return None
    return Video(
        video_id=video_id,
        title=snippet.get("title", ""),
        description=snippet.get("description", ""),
        channel_name=snippet.get("videoOwnerChannelTitle", ""),
        playlist_item_id=item.get("id"),
    )


def _chunks(lst: list, n: int):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
