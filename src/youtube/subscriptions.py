import structlog
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from tenacity import retry, stop_after_attempt, wait_exponential


log = structlog.get_logger()


class SubscriptionsFetcher:
    """Fetch the authenticated user's subscribed channels."""

    def __init__(self, credentials: Credentials) -> None:
        self._yt = build("youtube", "v3", credentials=credentials)

    def fetch_channel_names(self) -> set[str]:
        """Return a set of channel names from the user's subscriptions."""
        names: set[str] = set()
        next_page_token: str | None = None

        while True:
            try:
                response = self._fetch_page(next_page_token)
            except HttpError as e:
                log.error("Failed to fetch subscriptions", error=str(e))
                break

            for item in response.get("items", []):
                title = item.get("snippet", {}).get("title", "").strip()
                if title:
                    names.add(title)

            next_page_token = response.get("nextPageToken")
            if not next_page_token:
                break

        log.info("Fetched subscriptions", count=len(names))
        return names

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
    def _fetch_page(self, page_token: str | None) -> dict:
        return (
            self._yt.subscriptions()
            .list(
                part="snippet",
                mine=True,
                maxResults=50,
                order="alphabetical",
                pageToken=page_token,
            )
            .execute()
        )
