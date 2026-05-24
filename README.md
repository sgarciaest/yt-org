# yt-org

Classifies your YouTube Watch Later videos and proposes moving them into topic playlists (`WL/<topic>`). Nothing happens automatically — the workflow is always **analyze → review → apply**.

---

## Setup

Place `client_secrets.json` (Google OAuth credentials) in the project root. On first run requiring OAuth, a browser window will open to authorize access.

---

## Workflow

### 1. Build the channel map (recommended first step)

Populate `config/channel_topics.yaml` with channels from your subscriptions and/or your Watch Later file, then assign a topic to each channel you recognize. This boosts classification accuracy significantly.

```bash
# From your subscriptions list (requires OAuth)
yt-org channels --from-subscriptions

# From a Watch Later export file
yt-org channels --from-file "Watch later-vídeos.csv"

# Both at once (most useful)
yt-org channels --from-subscriptions --from-file "Watch later-vídeos.csv"
```

Then open `config/channel_topics.yaml` and set `topic: null` → `topic: <name>` for channels you recognize.

---

### 2. Analyze

Classify the Watch Later videos and generate a proposal.

```bash
# From a Google Takeout CSV (recommended)
yt-org analyze --from-file "Watch later-vídeos.csv"
```

This creates a new run folder under `runs/` (e.g. `runs/0013-2026-05-22/`) with a `proposal.yaml` listing every video and its proposed action:

| Action | Meaning |
|--------|---------|
| `move` | Score ≥ 0.75 — confident enough to move automatically |
| `review` | Score 0.35–0.75 — needs your decision |
| `keep` | Score < 0.35 — stays in Watch Later |

---

### 3. Review and edit the plan

```bash
cp runs/0013-2026-05-22/proposal.yaml runs/0013-2026-05-22/plan.yaml
```

Open `plan.yaml` and for each `action: review` entry, change it to `action: move` or `action: keep`. You can also change `predicted_topic` if the classification was wrong.

---

### 4. Apply

```bash
# Preview without making any changes
yt-org apply 13 --dry-run

# Apply to your YouTube account (will prompt for confirmation)
yt-org apply 13
```

Videos with `action: move` are added to their `WL/<topic>` playlist and removed from Watch Later automatically.

> **Note:** Automatic removal requires that videos were loaded via the YouTube API (which provides a `playlist_item_id`). Videos loaded from a Google Takeout CSV do not include this ID, so Watch Later removal is skipped for those — remove them manually.

---

## Other commands

```bash
# List all runs and their status
yt-org list

# Show summary for a specific run
yt-org show 13
```

---

## Topics

Topics are defined in `config/topics.yaml`. Each entry has a name and a description used for embedding-based classification. To add a new topic, add an entry there — no code changes needed.
