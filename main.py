import csv
import json
import sys
from pathlib import Path

# src/ is the package root for all application modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

import click
import structlog
import yaml

from classification.embeddings import EmbeddingClassifier
from config import load_config, load_topics_config
from domain.topic import Topic
from domain.video import Video
from storage.proposal_io import load_proposal, save_proposal
from storage.run_io import append_history, save_applied
from storage.run_manager import Run, create_run, list_runs, resolve_run
from workflow.analyze import run_analysis
from workflow.apply import run_apply
from youtube.auth import get_credentials
from youtube.client import YouTubeClient
from youtube.playlists import PlaylistManager


structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ]
)

log = structlog.get_logger()

RUNS_DIR = Path("runs")


@click.group()
def cli() -> None:
    """Organize YouTube Watch Later videos into topic playlists."""


@cli.command()
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option("--topics", default="config/topics.yaml", show_default=True)
@click.option(
    "--from-file",
    default=None,
    metavar="FILE",
    help="Load videos from a CSV (Takeout), YAML, or JSON file instead of the YouTube API",
)
def analyze(config: str, topics: str, from_file: str | None) -> None:
    """Create a new run and classify Watch Later videos into a proposal."""
    cfg = load_config(config)
    topic_list = _build_topics(topics)

    run = create_run(RUNS_DIR)
    log.info("Created run", run=run.name, folder=str(run.folder))

    if from_file:
        videos = _load_videos_from_file(from_file)
        log.info("Loaded videos from file", path=from_file, count=len(videos))
        try:
            credentials = get_credentials(
                cfg.youtube.client_secrets_file, cfg.youtube.token_file
            )
            yt_client = YouTubeClient(credentials)
            log.info("Enriching metadata from YouTube API…")
            videos = yt_client.enrich_videos(videos)
        except FileNotFoundError:
            log.info("No credentials — classifying with available data only")
    else:
        credentials = get_credentials(
            cfg.youtube.client_secrets_file, cfg.youtube.token_file
        )
        yt = YouTubeClient(credentials)
        videos = yt.get_watch_later_videos()

        if not videos:
            click.echo(
                "No videos returned from Watch Later.\n"
                "The YouTube API restricts Watch Later access.\n"
                "Export your Watch Later playlist and run:\n"
                "  yt-org analyze --from-file watch_later.csv",
                err=True,
            )
            run.folder.rmdir()
            sys.exit(1)

        log.info("Enriching video metadata…")
        videos = yt.enrich_videos(videos)

    classifier = EmbeddingClassifier(
        model_name=cfg.classification.model,
        weights=cfg.classification.weights.as_dict(),
    )

    proposal = run_analysis(videos, topic_list, classifier, cfg)
    save_proposal(proposal, run.proposal_path)

    move_count = sum(1 for v in proposal.videos if v.action == "move")
    review_count = sum(1 for v in proposal.videos if v.action == "review")
    keep_count = sum(1 for v in proposal.videos if v.action == "keep")

    click.echo(f"\nRun {run.id} created  →  {run.folder}/")
    click.echo(f"  proposal.yaml  ({len(proposal.videos)} videos)")
    click.echo(f"  move:    {move_count}")
    click.echo(f"  review:  {review_count}  ← needs human decision")
    click.echo(f"  keep:    {keep_count}")
    click.echo(f"\nNext steps:")
    click.echo(f"  1. Copy proposal → plan:")
    click.echo(f"       cp {run.proposal_path} {run.plan_path}")
    click.echo(f"  2. Edit {run.plan_path}")
    click.echo(f"       Change action: review  →  move  or  keep")
    click.echo(f"       Optionally change predicted_topic")
    click.echo(f"  3. Apply:")
    click.echo(f"       yt-org apply {run.id}")


@cli.command()
@click.argument("run_id")
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be done without modifying YouTube"
)
def apply(run_id: str, config: str, dry_run: bool) -> None:
    """Apply an approved plan to YouTube. RUN_ID: run number (e.g. 1 or 0001)."""
    cfg = load_config(config)

    try:
        run = resolve_run(run_id, RUNS_DIR)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    if run.applied_path.exists() and not dry_run:
        click.echo(
            f"Run {run.id} has already been applied ({run.applied_path}).\n"
            "Use --dry-run to inspect it, or start a new run with: yt-org analyze",
            err=True,
        )
        sys.exit(1)

    if not run.plan_path.exists():
        click.echo(
            f"No plan.yaml found in {run.folder}/\n"
            f"Copy the proposal first:\n"
            f"  cp {run.proposal_path} {run.plan_path}",
            err=True,
        )
        sys.exit(1)

    plan = load_proposal(run.plan_path)
    to_move = [vp for vp in plan.videos if vp.action == "move" and vp.predicted_topic]

    if not to_move:
        click.echo("No videos with action: move in plan.yaml. Nothing to do.")
        return

    click.echo(f"\nRun {run.id}  |  {run.date}  |  {run.plan_path}")
    click.echo(f"Videos to add to topic playlists: {len(to_move)}\n")
    for vp in to_move:
        click.echo(f"  [{vp.video_id}] {vp.title!r}  →  WL/{vp.predicted_topic}")

    if dry_run:
        click.echo("\n[dry-run] No changes made.")
        return

    click.confirm(f"\nApply {len(to_move)} changes to your YouTube account?", abort=True)

    credentials = get_credentials(cfg.youtube.client_secrets_file, cfg.youtube.token_file)
    manager = PlaylistManager(credentials)
    applied = run_apply(plan, manager, run_id=run.id, dry_run=False)

    save_applied(applied, run.applied_path)
    append_history(applied, RUNS_DIR / "history.yaml")

    click.echo(f"\nDone. {applied.total_moved} videos moved.")
    click.echo(f"Run audit  →  {run.applied_path}")
    click.echo(f"History    →  {RUNS_DIR / 'history.yaml'}")

    errors = [c for c in applied.changes if c.status == "error"]
    if errors:
        click.echo(f"\n{len(errors)} error(s) — check {run.applied_path} for details", err=True)

    click.echo("\nVideos are now in their topic playlists.")
    click.echo("You can manually remove them from Watch Later.")


@cli.command(name="list")
def list_command() -> None:
    """List all runs and their status."""
    runs = list_runs(RUNS_DIR)
    if not runs:
        click.echo("No runs yet. Start with: yt-org analyze")
        return

    click.echo(f"\n  {'#':<6} {'Date':<14} {'Proposal':<10} {'Plan':<8} Applied")
    click.echo("  " + "-" * 50)
    for run in runs:
        p = "✓" if run.proposal_path.exists() else "-"
        pl = "✓" if run.plan_path.exists() else "-"
        ap, detail = "-", ""
        if run.applied_path.exists():
            ap = "✓"
            try:
                data = yaml.safe_load(run.applied_path.read_text()) or {}
                detail = f"  ({data.get('total_moved', '?')} moved)"
            except Exception:
                pass
        click.echo(f"  {run.id:<6} {run.date.isoformat():<14} {p:<10} {pl:<8} {ap}{detail}")
    click.echo()


@cli.command()
@click.argument("run_id")
def show(run_id: str) -> None:
    """Show the proposal and plan summary for a run."""
    try:
        run = resolve_run(run_id, RUNS_DIR)
    except FileNotFoundError as e:
        click.echo(str(e), err=True)
        sys.exit(1)

    click.echo(f"\nRun {run.id}  —  {run.date}  —  {run.folder}/\n")

    for label, path in [("proposal.yaml", run.proposal_path), ("plan.yaml", run.plan_path)]:
        if not path.exists():
            click.echo(f"  {label}: not found")
            continue
        try:
            data = yaml.safe_load(path.read_text()) or {}
            videos = data.get("videos", [])
            counts = {a: sum(1 for v in videos if v.get("action") == a) for a in ("move", "review", "keep")}
            click.echo(f"  {label}: {len(videos)} videos  |  move {counts['move']}  review {counts['review']}  keep {counts['keep']}")
        except Exception as e:
            click.echo(f"  {label}: error reading — {e}")

    if run.applied_path.exists():
        try:
            data = yaml.safe_load(run.applied_path.read_text()) or {}
            click.echo(f"  applied.yaml: {data.get('total_moved', '?')} moved  at {data.get('applied_at', '?')}")
        except Exception as e:
            click.echo(f"  applied.yaml: error reading — {e}")
    else:
        click.echo("  applied.yaml: not yet applied")

    click.echo()


def _build_topics(topics_path: str) -> list[Topic]:
    raw = load_topics_config(topics_path)
    return [Topic(name=name, description=desc) for name, desc in raw.items()]


def _load_videos_from_file(path: str) -> list[Video]:
    p = Path(path)
    if p.suffix == ".csv":
        return _load_takeout_csv(p)
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f) if p.suffix in (".yaml", ".yml") else json.load(f)
    raw = data.get("videos", data) if isinstance(data, dict) else data
    return [
        Video(
            video_id=item.get("video_id", item.get("id", "")),
            title=item.get("title", ""),
            description=item.get("description", ""),
            tags=item.get("tags", []),
            channel_name=item.get("channel_name", item.get("channel", "")),
            category_id=item.get("category_id"),
        )
        for item in raw
    ]


def _load_takeout_csv(path: Path) -> list[Video]:
    """Parse a Google Takeout Watch Later CSV (Video ID, Timestamp columns)."""
    with path.open(encoding="utf-8", newline="") as f:
        lines = [l for l in f.readlines() if not l.lstrip().startswith("#")]
    videos: list[Video] = []
    for row in csv.DictReader(lines):
        # Google Takeout uses Spanish or English column names depending on account language
        video_id = (
            row.get("Video ID")
            or row.get("video_id")
            or row.get("ID de vídeo")
            or row.get("ID de video")
            or ""
        ).strip()
        if video_id:
            videos.append(Video(video_id=video_id, title=""))
    return videos


if __name__ == "__main__":
    cli()
