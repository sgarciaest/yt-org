import tempfile
from datetime import datetime, timezone
from pathlib import Path

import yaml

from domain.proposal import Proposal, VideoProposal
from storage.proposal_io import load_proposal, save_proposal


def _sample_proposal() -> Proposal:
    return Proposal(
        generated_at=datetime(2026, 5, 21, 10, 0, 0, tzinfo=timezone.utc),
        move_threshold=0.82,
        review_threshold=0.60,
        videos=[
            VideoProposal(
                video_id="abc123",
                title="How to improve climbing footwork",
                predicted_topic="escalada",
                confidence=0.91,
                alternatives={"escalada": 0.91, "fotografía": 0.41},
                action="move",
                playlist_item_id="PLItem123",
            ),
            VideoProposal(
                video_id="xyz456",
                title="Random documentary",
                predicted_topic=None,
                confidence=0.42,
                alternatives={"comida": 0.42, "música": 0.30},
                action="keep",
            ),
        ],
    )


def test_round_trip() -> None:
    proposal = _sample_proposal()
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    try:
        save_proposal(proposal, path)
        loaded = load_proposal(path)

        assert len(loaded.videos) == 2
        assert loaded.videos[0].video_id == "abc123"
        assert loaded.videos[0].action == "move"
        assert loaded.videos[0].predicted_topic == "escalada"
        assert loaded.videos[0].playlist_item_id == "PLItem123"
        assert loaded.videos[1].action == "keep"
        assert loaded.videos[1].predicted_topic is None
        assert loaded.move_threshold == 0.82
        assert loaded.review_threshold == 0.60
    finally:
        path.unlink(missing_ok=True)


def test_yaml_output_is_human_readable() -> None:
    proposal = _sample_proposal()
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False, mode="w") as f:
        path = Path(f.name)

    try:
        save_proposal(proposal, path)
        content = path.read_text()
        parsed = yaml.safe_load(content)

        # Key editable fields are top-level in each video entry
        assert "action" in content
        assert "predicted_topic" in content
        assert "abc123" in content
        assert parsed["thresholds"]["auto_move"] == 0.82
    finally:
        path.unlink(missing_ok=True)


def test_manual_topic_override_preserved() -> None:
    """A human editing predicted_topic in the YAML is preserved on load."""
    proposal = _sample_proposal()
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
        path = Path(f.name)

    try:
        save_proposal(proposal, path)

        # Simulate a human editing the YAML
        data = yaml.safe_load(path.read_text())
        data["videos"][1]["predicted_topic"] = "música"
        data["videos"][1]["action"] = "move"
        path.write_text(yaml.dump(data, allow_unicode=True))

        loaded = load_proposal(path)
        assert loaded.videos[1].predicted_topic == "música"
        assert loaded.videos[1].action == "move"
    finally:
        path.unlink(missing_ok=True)
