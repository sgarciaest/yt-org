import pytest

from classification.channel_mapper import ChannelMapper
from classification.classifier import ClassificationResult


MAPPING = {
    "Lattice Training": "escalada",
    "Ben Felix": "inversión",
    "Boris Hajduk": "darktable",
}
BONUS = 0.25


@pytest.fixture
def mapper() -> ChannelMapper:
    return ChannelMapper(MAPPING, BONUS)


class TestLookup:
    def test_exact_match(self, mapper: ChannelMapper) -> None:
        assert mapper.lookup("Lattice Training") == "escalada"

    def test_case_insensitive(self, mapper: ChannelMapper) -> None:
        assert mapper.lookup("lattice training") == "escalada"
        assert mapper.lookup("LATTICE TRAINING") == "escalada"
        assert mapper.lookup("Lattice TRAINING") == "escalada"

    def test_no_match_returns_none(self, mapper: ChannelMapper) -> None:
        assert mapper.lookup("Unknown Channel") is None

    def test_empty_string_returns_none(self, mapper: ChannelMapper) -> None:
        assert mapper.lookup("") is None


class TestApplyBoost:
    def test_boost_raises_score_for_matched_topic(self, mapper: ChannelMapper) -> None:
        result = ClassificationResult({"escalada": 0.62, "fotografía": 0.30})
        boosted = mapper.apply_boost("Lattice Training", result)
        assert boosted.scores["escalada"] == pytest.approx(0.62 + BONUS)
        assert boosted.scores["fotografía"] == pytest.approx(0.30)  # unchanged

    def test_boost_can_cross_threshold(self, mapper: ChannelMapper) -> None:
        # AI score alone is in review band; boost should push it to move
        result = ClassificationResult({"escalada": 0.55, "fotografía": 0.20})
        boosted = mapper.apply_boost("Lattice Training", result)
        assert boosted.scores["escalada"] == pytest.approx(0.55 + BONUS)

    def test_no_match_returns_original_unchanged(self, mapper: ChannelMapper) -> None:
        result = ClassificationResult({"escalada": 0.62, "fotografía": 0.30})
        boosted = mapper.apply_boost("Unknown Channel", result)
        assert boosted.scores == result.scores

    def test_boost_clips_at_one(self, mapper: ChannelMapper) -> None:
        result = ClassificationResult({"escalada": 0.90, "fotografía": 0.20})
        boosted = mapper.apply_boost("Lattice Training", result)
        assert boosted.scores["escalada"] == pytest.approx(1.0)

    def test_boost_does_not_clip_when_under_one(self, mapper: ChannelMapper) -> None:
        result = ClassificationResult({"escalada": 0.50, "fotografía": 0.20})
        boosted = mapper.apply_boost("Lattice Training", result)
        assert boosted.scores["escalada"] == pytest.approx(0.50 + BONUS)

    def test_zero_bonus_returns_original(self) -> None:
        mapper_zero = ChannelMapper(MAPPING, bonus=0.0)
        result = ClassificationResult({"escalada": 0.62})
        boosted = mapper_zero.apply_boost("Lattice Training", result)
        assert boosted.scores["escalada"] == pytest.approx(0.62)

    def test_unknown_topic_in_mapping_skips_boost(self) -> None:
        bad_mapper = ChannelMapper({"Some Channel": "nonexistent_topic"}, BONUS)
        result = ClassificationResult({"escalada": 0.62})
        boosted = bad_mapper.apply_boost("Some Channel", result)
        # Should return original unchanged, not crash
        assert boosted.scores == result.scores

    def test_original_result_not_mutated(self, mapper: ChannelMapper) -> None:
        original_scores = {"escalada": 0.62, "fotografía": 0.30}
        result = ClassificationResult(dict(original_scores))
        mapper.apply_boost("Lattice Training", result)
        assert result.scores == original_scores  # original unchanged


class TestMergeChannelMap:
    """Test the channel map IO merge logic."""

    def test_merge_adds_new_channels(self) -> None:
        from datetime import date
        from storage.channel_map_io import merge_channels

        existing = {"Lattice Training": {"topic": "escalada", "added_at": "2026-01-01"}}
        merged, added = merge_channels(existing, {"Ben Felix", "Lattice Training"}, date(2026, 5, 22))

        assert added == 1
        assert "Ben Felix" in merged
        assert merged["Ben Felix"]["topic"] is None
        assert merged["Ben Felix"]["added_at"] == "2026-05-22"

    def test_merge_preserves_existing_topic(self) -> None:
        from datetime import date
        from storage.channel_map_io import merge_channels

        existing = {"Lattice Training": {"topic": "escalada", "added_at": "2026-01-01"}}
        merged, _ = merge_channels(existing, {"Lattice Training"}, date(2026, 5, 22))

        assert merged["Lattice Training"]["topic"] == "escalada"
        assert merged["Lattice Training"]["added_at"] == "2026-01-01"

    def test_merge_empty_existing(self) -> None:
        from datetime import date
        from storage.channel_map_io import merge_channels

        merged, added = merge_channels({}, {"Channel A", "Channel B"}, date(2026, 5, 22))
        assert added == 2
        assert len(merged) == 2
