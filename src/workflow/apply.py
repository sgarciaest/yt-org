import structlog
from datetime import datetime, timezone

from domain.proposal import Proposal
from domain.run import AppliedChange, AppliedLog
from youtube.playlists import PlaylistManager


log = structlog.get_logger()


def run_apply(
    plan: Proposal,
    playlist_manager: PlaylistManager,
    run_id: str,
    dry_run: bool = False,
) -> AppliedLog:
    to_move = [vp for vp in plan.videos if vp.action == "move" and vp.predicted_topic]
    skipped = len(plan.videos) - len(to_move)

    log.info("Apply plan", to_move=len(to_move), skipped=skipped, dry_run=dry_run)

    changes: list[AppliedChange] = []

    for vp in to_move:
        playlist_name = f"WL/{vp.predicted_topic}"
        log.info("Moving video", title=vp.title[:60], playlist=playlist_name, dry_run=dry_run)

        if dry_run:
            continue

        try:
            playlist_id = playlist_manager.ensure_playlist(playlist_name)
            playlist_manager.add_video(vp.video_id, playlist_id)
            wl_removed = playlist_manager.remove_from_watch_later(vp.video_id, vp.playlist_item_id)
            changes.append(
                AppliedChange(
                    video_id=vp.video_id,
                    title=vp.title,
                    playlist=playlist_name,
                    status="added",
                    applied_at=datetime.now(timezone.utc),
                    wl_removed=wl_removed,
                )
            )
        except Exception as e:
            log.error("Failed to move video", video_id=vp.video_id, error=str(e))
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
    log.info("Apply complete", total_moved=applied.total_moved, dry_run=dry_run)
    return applied
