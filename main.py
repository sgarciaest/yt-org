import sys
from datetime import datetime, timezone
from pathlib import Path

# src/ is the package root for all application modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

import click
import structlog
import yaml

from classification.channel_mapper import ChannelMapper
from classification.embeddings import EmbeddingClassifier
from config import load_channel_mapping, load_config, load_topics_config
from domain.topic import Topic
from domain.video import Video
from sources.file_source import FileSource
from sources.yt_api_source import YouTubeAPISource
from sources.yt_dlp_source import YtDlpSource
from storage.channel_map_io import load_channel_map, merge_channels, save_channel_map
from storage.proposal_io import load_proposal, save_proposal
from storage.run_io import append_history, save_applied, save_run_meta
from storage.run_manager import create_run, list_runs, resolve_run
from workflow.analyze import run_analysis
from workflow.apply import run_apply
from youtube.auth import get_credentials
from youtube.client import YouTubeClient
from youtube.playlists import PlaylistManager
from youtube.subscriptions import SubscriptionsFetcher


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
    help="CSV (Google Takeout), YAML, or JSON file with Watch Later videos",
)
@click.option(
    "--from-yt-api",
    is_flag=True,
    default=False,
    help="YouTube Data API v3 (currently blocked by Google for Watch Later)",
)
@click.option(
    "--from-yt-dlp",
    is_flag=True,
    default=False,
    help="yt-dlp with browser cookies (not yet implemented)",
)
def analyze(
    config: str,
    topics: str,
    from_file: str | None,
    from_yt_api: bool,
    from_yt_dlp: bool,
) -> None:
    """Create a new run and classify Watch Later videos into a proposal.

    Exactly one source flag must be provided.
    """
    cfg = load_config(config)
    topic_list = _build_topics(topics)

    # --- validate source selection ---
    sources_given = sum([bool(from_file), from_yt_api, from_yt_dlp])
    if sources_given == 0:
        raise click.UsageError(
            "Specify a source:\n"
            "  --from-file <path>   Google Takeout CSV, YAML, or JSON  [recommended]\n"
            "  --from-yt-api        YouTube Data API v3  [currently blocked by Google]\n"
            "  --from-yt-dlp        yt-dlp with browser cookies  [not yet implemented]"
        )
    if sources_given > 1:
        raise click.UsageError("Only one source flag may be used at a time.")

    # --- build source ---
    credentials = _load_credentials_if_available(cfg)

    if from_file:
        source = FileSource(Path(from_file))
    elif from_yt_api:
        if credentials is None:
            raise click.UsageError(
                "client_secrets.json not found. "
                "OAuth credentials are required for --from-yt-api."
            )
        source = YouTubeAPISource(YouTubeClient(credentials))
    else:
        source = YtDlpSource()

    # --- fetch ---
    run = create_run(RUNS_DIR)
    log.info("Created run", run=run.name, source=source.source_name)

    try:
        videos = source.fetch()
    except (RuntimeError, NotImplementedError) as e:
        click.echo(str(e), err=True)
        run.folder.rmdir()
        sys.exit(1)

    log.info("Fetched videos", source=source.source_name, count=len(videos))

    # --- enrich: fill title/description/tags/channel via videos.list ---
    # Always attempted when credentials are available; idempotent for already-complete videos.
    if credentials is not None:
        log.info("Enriching metadata from YouTube API…")
        videos = YouTubeClient(credentials).enrich_videos(videos)
    else:
        log.warning("No YouTube credentials — skipping enrichment, classification quality may be lower")

    # --- classify ---
    classifier = EmbeddingClassifier(
        model_name=cfg.classification.model,
        weights=cfg.classification.weights.as_dict(),
    )
    channel_mapping = load_channel_mapping(cfg.channel_mapping.config_file)
    channel_mapper = (
        ChannelMapper(channel_mapping, cfg.channel_mapping.bonus)
        if channel_mapping
        else None
    )
    if channel_mapper:
        log.info("Channel mapping loaded", channels=channel_mapper.size)
    else:
        log.info("No channel mapping found — using AI only", hint=f"Run: yt-org channels --help")

    proposal = run_analysis(videos, topic_list, classifier, cfg, channel_mapper)
    save_proposal(proposal, run.proposal_path)

    move_count = sum(1 for v in proposal.videos if v.action == "move")
    review_count = sum(1 for v in proposal.videos if v.action == "review")
    keep_count = sum(1 for v in proposal.videos if v.action == "keep")

    # Videos with no title after enrichment are private/deleted/region-blocked
    missing = sum(1 for v in videos if not v.title)
    save_run_meta(
        {
            "run_id": run.id,
            "analyzed_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            "source": {
                "name": source.source_name,
                **({"file": from_file} if from_file else {}),
            },
            "videos": {
                "fetched": len(videos),
                "enriched": len(videos) - missing,
                "missing": missing,
            },
            "proposal": {
                "total": len(proposal.videos),
                "move": move_count,
                "review": review_count,
                "keep": keep_count,
            },
            "classification": {
                "model": cfg.classification.model,
                "weights": cfg.classification.weights.as_dict(),
                "thresholds": {
                    "move": cfg.classification.thresholds.move,
                    "review": cfg.classification.thresholds.review,
                },
                "top_n_alternatives": cfg.classification.top_n_alternatives,
            },
            "channel_mapping": {
                "active": channel_mapper is not None,
                "bonus": cfg.channel_mapping.bonus,
                "mapped_channels": channel_mapper.size if channel_mapper else 0,
            },
            "topics": {
                "count": len(topic_list),
                "names": [t.name for t in topic_list],
            },
        },
        run.meta_path,
    )

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
        click.echo("No runs yet. Start with: yt-org analyze --from-file <path>")
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

    if run.meta_path.exists():
        try:
            m = yaml.safe_load(run.meta_path.read_text()) or {}
            src = m.get("source", {})
            vids = m.get("videos", {})
            cl = m.get("classification", {})
            th = cl.get("thresholds", {})
            cm = m.get("channel_mapping", {})
            src_label = src.get("name", src.get("type", "?"))
            if src.get("file"):
                src_label += f" ({src['file']})"
            enriched_info = f"{vids.get('fetched', '?')} fetched"
            if vids.get("missing", 0):
                enriched_info += f" ({vids['missing']} missing)"
            click.echo(
                f"  meta.yaml:     {src_label} | {enriched_info} | "
                f"move≥{th.get('move', '?')} review≥{th.get('review', '?')} | "
                f"bonus={cm.get('bonus', '?')} ({cm.get('mapped_channels', 0)} channels)"
            )
        except Exception as e:
            click.echo(f"  meta.yaml: error reading — {e}")
    else:
        click.echo("  meta.yaml: not found (run predates this feature)")

    for label, path in [("proposal.yaml", run.proposal_path), ("plan.yaml", run.plan_path)]:
        if not path.exists():
            click.echo(f"  {label}: not found")
            continue
        try:
            data = yaml.safe_load(path.read_text()) or {}
            videos = data.get("videos", [])
            counts = {
                a: sum(1 for v in videos if v.get("action") == a)
                for a in ("move", "review", "keep")
            }
            click.echo(
                f"  {label}: {len(videos)} videos  |  "
                f"move {counts['move']}  review {counts['review']}  keep {counts['keep']}"
            )
        except Exception as e:
            click.echo(f"  {label}: error reading — {e}")

    if run.applied_path.exists():
        try:
            data = yaml.safe_load(run.applied_path.read_text()) or {}
            click.echo(
                f"  applied.yaml: {data.get('total_moved', '?')} moved"
                f"  at {data.get('applied_at', '?')}"
            )
        except Exception as e:
            click.echo(f"  applied.yaml: error reading — {e}")
    else:
        click.echo("  applied.yaml: not yet applied")

    click.echo()


@cli.command()
@click.option("--config", default="config/settings.yaml", show_default=True)
@click.option(
    "--from-subscriptions",
    is_flag=True,
    default=False,
    help="Add channels from your YouTube subscriptions list",
)
@click.option(
    "--from-file",
    default=None,
    metavar="FILE",
    help="Add channels found in a Watch Later file (CSV/YAML/JSON)",
)
@click.option(
    "--from-yt-api",
    is_flag=True,
    default=False,
    help="Add channels found in Watch Later via YouTube API (currently blocked by Google)",
)
@click.option(
    "--output",
    default=None,
    metavar="PATH",
    help="Output file (default: channel_mapping.config_file from settings)",
)
def channels(
    config: str,
    from_subscriptions: bool,
    from_file: str | None,
    from_yt_api: bool,
    output: str | None,
) -> None:
    """Build or update the channel-to-topic mapping config.

    Collects channel names from the chosen sources, merges them into
    config/channel_topics.yaml (preserving any existing topic assignments),
    and adds new entries with topic: null for you to fill in.

    At least one source flag is required. Multiple flags can be combined.
    """
    cfg = load_config(config)
    out_path = Path(output or cfg.channel_mapping.config_file)

    if not from_subscriptions and not from_file and not from_yt_api:
        raise click.UsageError(
            "Specify at least one source:\n"
            "  --from-subscriptions   Your YouTube subscriptions\n"
            "  --from-file <path>     Watch Later CSV/YAML/JSON\n"
            "  --from-yt-api          Watch Later via YouTube API (blocked)"
        )

    credentials = _load_credentials_if_available(cfg)
    collected: set[str] = set()

    # --- subscriptions ---
    if from_subscriptions:
        if credentials is None:
            raise click.UsageError(
                "client_secrets.json not found. OAuth is required for --from-subscriptions."
            )
        log.info("Fetching subscriptions…")
        fetcher = SubscriptionsFetcher(credentials)
        subs = fetcher.fetch_channel_names()
        log.info("Subscriptions fetched", count=len(subs))
        collected |= subs

    # --- watch later channels ---
    wl_source = None
    if from_file:
        wl_source = FileSource(Path(from_file))
    elif from_yt_api:
        if credentials is None:
            raise click.UsageError(
                "client_secrets.json not found. OAuth is required for --from-yt-api."
            )
        wl_source = YouTubeAPISource(YouTubeClient(credentials))

    if wl_source is not None:
        try:
            videos = wl_source.fetch()
        except (RuntimeError, NotImplementedError) as e:
            click.echo(str(e), err=True)
            raise SystemExit(1)

        if credentials is not None:
            log.info("Enriching video metadata to extract channel names…")
            videos = YouTubeClient(credentials).enrich_videos(videos)

        wl_channels = {v.channel_name for v in videos if v.channel_name}
        log.info("Channels extracted from Watch Later", count=len(wl_channels))
        collected |= wl_channels

    if not collected:
        click.echo("No channels found from the given sources. Nothing written.")
        return

    # --- merge with existing ---
    existing = load_channel_map(out_path)
    merged, added = merge_channels(existing, collected)
    save_channel_map(merged, out_path)

    total = len(merged)
    null_count = sum(1 for v in merged.values() if not v.get("topic"))
    assigned_count = total - null_count

    click.echo(f"\nChannel map updated  →  {out_path}")
    click.echo(f"  total channels:  {total}")
    click.echo(f"  newly added:     {added}")
    click.echo(f"  with topic:      {assigned_count}")
    click.echo(f"  needs topic:     {null_count}  ← open {out_path} and fill these in")

    if null_count:
        topics_hint = _load_topic_names(cfg)
        click.echo(f"\nAvailable topics: {', '.join(topics_hint)}")
        click.echo("Set topic: null → topic: <name> for channels you recognise.")


def _load_topic_names(cfg) -> list[str]:
    try:
        from config import load_topics_config
        return list(load_topics_config().keys())
    except Exception:
        return []


def _build_topics(topics_path: str) -> list[Topic]:
    raw = load_topics_config(topics_path)
    return [Topic(name=name, description=desc) for name, desc in raw.items()]


def _load_credentials_if_available(cfg) -> object | None:
    """Return credentials if client_secrets.json exists, None otherwise."""
    try:
        return get_credentials(cfg.youtube.client_secrets_file, cfg.youtube.token_file)
    except FileNotFoundError:
        return None


if __name__ == "__main__":
    cli()
