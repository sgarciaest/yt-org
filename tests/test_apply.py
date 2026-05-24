from datetime import datetime, timezone

from domain.proposal import Proposal, VideoProposal
from workflow.apply import run_apply


class _FakePlaylistManager:
    def __init__(self) -> None:
        self.adds: list[tuple[str, str]] = []  # (video_id, playlist_name)
        self._ids: dict[str, str] = {}

    def ensure_playlist(self, name: str) -> str:
        self._ids.setdefault(name, f"PLID-{name}")
        return self._ids[name]

    def add_video(self, video_id: str, playlist_id: str) -> None:
        # Recover the playlist name from the fake id
        name = next(n for n, i in self._ids.items() if i == playlist_id)
        self.adds.append((video_id, name))


def _vp(video_id: str, action: str, topic: str | None = None) -> VideoProposal:
    return VideoProposal(
        video_id=video_id,
        title=f"title-{video_id}",
        predicted_topic=topic,
        confidence=0.5,
        alternatives={},
        action=action,  # type: ignore[arg-type]
    )


def _plan(*videos: VideoProposal) -> Proposal:
    return Proposal(
        generated_at=datetime(2026, 5, 24, tzinfo=timezone.utc),
        move_threshold=0.75,
        review_threshold=0.35,
        videos=list(videos),
    )


def test_move_with_topic_goes_to_topic_playlist() -> None:
    pm = _FakePlaylistManager()
    plan = _plan(_vp("v1", "move", topic="escalada"))
    applied = run_apply(plan, pm, run_id="0001", fallback_name="general")
    assert pm.adds == [("v1", "WL/escalada")]
    assert applied.total_moved == 1


def test_keep_goes_to_fallback() -> None:
    pm = _FakePlaylistManager()
    plan = _plan(_vp("v2", "keep"))
    applied = run_apply(plan, pm, run_id="0001", fallback_name="general")
    assert pm.adds == [("v2", "WL/general")]
    assert applied.total_moved == 1


def test_unresolved_review_goes_to_fallback() -> None:
    pm = _FakePlaylistManager()
    plan = _plan(_vp("v3", "review", topic="comida"))
    applied = run_apply(plan, pm, run_id="0001", fallback_name="general")
    # review is silently treated as keep regardless of predicted_topic
    assert pm.adds == [("v3", "WL/general")]
    assert applied.total_moved == 1


def test_move_without_topic_goes_to_fallback() -> None:
    pm = _FakePlaylistManager()
    plan = _plan(_vp("v4", "move", topic=None))
    applied = run_apply(plan, pm, run_id="0001", fallback_name="general")
    assert pm.adds == [("v4", "WL/general")]
    assert applied.total_moved == 1


def test_custom_fallback_name() -> None:
    pm = _FakePlaylistManager()
    plan = _plan(_vp("v5", "keep"))
    run_apply(plan, pm, run_id="0001", fallback_name="unsorted")
    assert pm.adds == [("v5", "WL/unsorted")]


def test_mixed_plan_routes_correctly_and_counts_total() -> None:
    pm = _FakePlaylistManager()
    plan = _plan(
        _vp("a", "move", topic="escalada"),
        _vp("b", "review", topic="comida"),
        _vp("c", "keep"),
        _vp("d", "move", topic=None),
        _vp("e", "move", topic="música"),
    )
    applied = run_apply(plan, pm, run_id="0001", fallback_name="general")

    assert pm.adds == [
        ("a", "WL/escalada"),
        ("b", "WL/general"),
        ("c", "WL/general"),
        ("d", "WL/general"),
        ("e", "WL/música"),
    ]
    assert applied.total_moved == 5
    assert all(c.status == "added" for c in applied.changes)


def test_dry_run_makes_no_calls() -> None:
    pm = _FakePlaylistManager()
    plan = _plan(_vp("v1", "move", topic="escalada"), _vp("v2", "keep"))
    applied = run_apply(plan, pm, run_id="0001", fallback_name="general", dry_run=True)
    assert pm.adds == []
    assert applied.total_moved == 0
    assert applied.changes == []
