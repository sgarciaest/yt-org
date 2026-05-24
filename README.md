# yt-org

Classifies your YouTube Watch Later videos and reorganizes them into topic playlists (`WL/<topic>`). Nothing happens automatically — the workflow is always **analyze → review → apply**.

After `apply`, **every** video in your input ends up in some `WL/*` playlist: confidently-classified ones go to `WL/<topic>`, the rest go to `WL/<fallback>` (default `WL/general`). You then manually clear the original Watch Later in the YouTube UI.

---

## Why a custom playlist?

YouTube's Data API cannot read or modify your built-in Watch Later. That's a Google-side restriction, not a bug in this tool. You have two ways to feed videos into yt-org:

1. **Export Watch Later as a CSV** from [takeout.google.com](https://takeout.google.com) → YouTube → playlists.
2. **Mirror Watch Later into a regular playlist** you create yourself (e.g. "My WL") — regular playlists are fully API-accessible, so yt-org can read them directly.

Either way, after applying, your original Watch Later still contains the videos. The final step is a manual UI cleanup.

---

## Setup

Place `client_secrets.json` (Google OAuth credentials) in the project root. On first run requiring OAuth, a browser window will open to authorize access.

---

## Workflow

### 1. Build the channel map (recommended first step)

Populate `config/channel_topics.yaml` with channels from your subscriptions and/or your Watch Later, then assign a topic to each channel you recognize. This boosts classification accuracy significantly.

```bash
# From your subscriptions list (requires OAuth)
yt-org channels --from-subscriptions

# From a Watch Later export file
yt-org channels --from-file "Watch later-vídeos.csv"

# From a user-owned playlist (ID or URL)
yt-org channels --from-user-playlist "https://www.youtube.com/playlist?list=PLrAXt..."

# Combine sources (most useful)
yt-org channels --from-subscriptions --from-file "Watch later-vídeos.csv"
```

Then open `config/channel_topics.yaml` and set `topic: null` → `topic: <name>` for channels you recognize.

---

### 2. Analyze

Classify the videos and generate a proposal.

```bash
# From a Google Takeout CSV (recommended)
yt-org analyze --from-file "Watch later-vídeos.csv"

# From a user-owned playlist that mirrors Watch Later
yt-org analyze --from-user-playlist "PLrAXt..."
```

This creates a new run folder under `runs/` (e.g. `runs/0013-2026-05-22/`) with a `proposal.yaml` listing every video and its proposed action:

| Action   | Meaning                                                                                |
|----------|----------------------------------------------------------------------------------------|
| `move`   | Score ≥ `thresholds.move` — confident enough to send to a topic playlist on apply.     |
| `review` | Score between the two thresholds — needs your decision in `plan.yaml`.                 |
| `keep`   | Score < `thresholds.review` — the classifier doesn't have a good guess.                |

---

### 3. Review and edit the plan

```bash
cp runs/0013-2026-05-22/proposal.yaml runs/0013-2026-05-22/plan.yaml
```

Open `plan.yaml` and for each `action: review` entry, change it to `action: move` (and optionally fix `predicted_topic`) or `action: keep`. Anything you don't resolve will be treated as `keep`.

---

### 4. Apply

```bash
# Preview without making any changes
yt-org apply 13 --dry-run

# Apply to your YouTube account (will prompt for confirmation)
yt-org apply 13
```

Every video in the plan is added to a `WL/*` playlist:

- `action: move` + a `predicted_topic` → `WL/<topic>`
- `action: keep`, `action: review`, or `move` without a topic → `WL/general` (configurable, see below)

After apply, **delete everything from your original Watch Later in the YouTube UI**. The API can't do this for you.

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

The fallback playlist name (used for `keep`/`review` videos) is set in `config/settings.yaml` under `playlists.fallback_name` (default: `general` → `WL/general`).
