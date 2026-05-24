import pytest

from sources.custom_playlist_source import CustomPlaylistSource


class _FakeClient:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_playlist_videos(self, playlist_id: str) -> list:
        self.calls.append(playlist_id)
        return []


def test_accepts_raw_playlist_id() -> None:
    src = CustomPlaylistSource("PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D", _FakeClient())
    assert src.playlist_id == "PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D"
    assert src.source_name == "playlist:PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D"


def test_extracts_id_from_full_url() -> None:
    url = "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D"
    src = CustomPlaylistSource(url, _FakeClient())
    assert src.playlist_id == "PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D"


def test_extracts_id_from_url_with_extra_params() -> None:
    url = (
        "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        "&list=PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D&index=2"
    )
    src = CustomPlaylistSource(url, _FakeClient())
    assert src.playlist_id == "PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D"


def test_rejects_garbage_input() -> None:
    with pytest.raises(RuntimeError, match="does not look like"):
        CustomPlaylistSource("not-a-real-id", _FakeClient())


def test_rejects_empty_input() -> None:
    with pytest.raises(RuntimeError, match="Empty"):
        CustomPlaylistSource("   ", _FakeClient())


def test_rejects_url_without_list_param() -> None:
    with pytest.raises(RuntimeError, match="`list=`"):
        CustomPlaylistSource("https://www.youtube.com/watch?v=dQw4w9WgXcQ", _FakeClient())


def test_fetch_calls_client_with_extracted_id() -> None:
    client = _FakeClient()
    src = CustomPlaylistSource(
        "https://www.youtube.com/playlist?list=PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D",
        client,
    )
    src.fetch()
    assert client.calls == ["PLrAXtmRdnEQy6nuLMfO6sUFCNGD9_l_3D"]
