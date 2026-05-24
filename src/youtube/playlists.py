import structlog
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential


log = structlog.get_logger()


class PlaylistManager:
    def __init__(self, credentials: Credentials) -> None:
        self._yt = build("youtube", "v3", credentials=credentials)
        self._cache: dict[str, str] = {}  # playlist title -> playlist_id

    def ensure_playlist(self, name: str) -> str:
        """Return the playlist ID for *name*, creating it if it does not exist."""
        if name in self._cache:
            return self._cache[name]

        existing = self._fetch_all_playlists()
        self._cache.update(existing)

        if name in self._cache:
            return self._cache[name]

        playlist_id = self._create_playlist(name)
        self._cache[name] = playlist_id
        log.info("Created playlist", name=name, playlist_id=playlist_id)
        return playlist_id

    def _fetch_all_playlists(self) -> dict[str, str]:
        playlists: dict[str, str] = {}
        next_page_token: str | None = None

        while True:
            try:
                response = (
                    self._yt.playlists()
                    .list(
                        part="snippet",
                        mine=True,
                        maxResults=50,
                        pageToken=next_page_token,
                    )
                    .execute()
                )
            except HttpError as e:
                log.error("Failed to list playlists", error=str(e))
                break

            for item in response.get("items", []):
                playlists[item["snippet"]["title"]] = item["id"]

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        return playlists

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def _create_playlist(self, name: str) -> str:
        response = (
            self._yt.playlists()
            .insert(
                part="snippet,status",
                body={
                    "snippet": {
                        "title": name,
                        "description": "Auto-organized from Watch Later by yt-org",
                    },
                    "status": {"privacyStatus": "private"},
                },
            )
            .execute()
        )
        return str(response["id"])

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def add_video(self, video_id: str, playlist_id: str) -> None:
        try:
            self._yt.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id,
                        },
                    }
                },
            ).execute()
            log.info("Added video to playlist", video_id=video_id, playlist_id=playlist_id)
        except HttpError as e:
            if e.resp.status == 409:
                log.debug("Video already in playlist, skipping", video_id=video_id)
                return
            raise

    def remove_from_watch_later(self, video_id: str, playlist_item_id: str | None) -> bool:
        """Remove a video from Watch Later. Returns True on success, False if skipped or failed."""
        if not playlist_item_id:
            log.warning(
                "Cannot remove from Watch Later: playlist_item_id unknown "
                "(CSV-loaded videos have no item ID — Watch Later is not listable via the API)",
                video_id=video_id,
            )
            return False
        try:
            self._delete_playlist_item(playlist_item_id)
            log.info("Removed from Watch Later", video_id=video_id)
            return True
        except HttpError as e:
            log.warning("Failed to remove from Watch Later", video_id=video_id, error=str(e))
            return False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def _delete_playlist_item(self, playlist_item_id: str) -> None:
        self._yt.playlistItems().delete(id=playlist_item_id).execute()
