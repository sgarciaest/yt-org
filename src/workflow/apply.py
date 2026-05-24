import structlog
from datetime import datetime, timezone

from domain.proposal import Proposal, VideoProposal
from domain.run import AppliedChange, AppliedLog
from youtube.playlists import PlaylistManager


log = structlog.get_logger()


def run_apply(
    plan: Proposal,
    playlist_manager: PlaylistManager,
    run_id: str,
    fallback_name: str,
    dry_run: bool = False,
) -> AppliedLog:
    to_topics = sum(1 for vp in plan.videos if _destination_topic(vp) is not None)
    to_fallback = len(plan.videos) - to_topics

    log.info(
        "Apply plan",
        total=len(plan.videos),
        to_topics=to_topics,
        to_fallback=to_fallback,
        fallback_name=fallback_name,
        dry_run=dry_run,
    )

    changes: list[AppliedChange] = []

    for vp in plan.videos:
        topic = _destination_topic(vp)
        playlist_name = f"WL/{topic}" if topic else f"WL/{fallback_name}"
        log.info("Adding video", title=vp.title[:60], playlist=playlist_name, dry_run=dry_run)

        if dry_run:
            continue

        try:
            playlist_id = playlist_manager.ensure_playlist(playlist_name)
            playlist_manager.add_video(vp.video_id, playlist_id)
            changes.append(
                AppliedChange(
                    video_id=vp.video_id,
                    title=vp.title,
                    playlist=playlist_name,
                    status="added",
                    applied_at=datetime.now(timezone.utc),
                )
            )
        except Exception as e:
            log.error("Failed to add video", video_id=vp.video_id, error=str(e))
            changes.append(
                AppliedChange(
                    video_id=vp.video_id,
                    title=vp.title,
                    playlist=playlist_name,
                    status="error",
                    applied_at=datetime.now(timezone.utc),
                    error=str(e),
                )
            )

    applied = AppliedLog(
        run_id=run_id,
        applied_at=datetime.now(timezone.utc),
        total_moved=sum(1 for c in changes if c.status == "added"),
        changes=changes,
    )
    log.info("Apply complete", total_added=applied.total_moved, dry_run=dry_run)
    return applied


def _destination_topic(vp: VideoProposal) -> str | None:
    """Return the topic name if the video routes to WL/<topic>, else None (→ fallback)."""
    if vp.action == "move" and vp.predicted_topic:
        return vp.predicted_topic
    return None
