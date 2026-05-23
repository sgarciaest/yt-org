"""
Integration tests for the embedding classifier.
These download the sentence-transformer model (~120 MB) on first run.
Mark with -m slow if you want to skip them in fast CI:
    pytest -m "not slow"
"""

import pytest

from classification.embeddings import EmbeddingClassifier
from domain.topic import Topic
from domain.video import Video


TOPICS = [
    Topic("escalada", "Rock climbing, bouldering, sport climbing, training, holds, gear, escalada"),
    Topic("inversión", "Investing, personal finance, ETFs, stock market, financial planning, inversión"),
    Topic("fotografía", "Photography, camera, composition, lighting, portrait, fotografía"),
    Topic("música", "Music, guitar, piano, music theory, concerts, production, música"),
    Topic("comida", "Cooking, recipes, food, gastronomy, baking, cocina, recetas"),
]


@pytest.fixture(scope="module")
def classifier() -> EmbeddingClassifier:
    clf = EmbeddingClassifier()
    clf.fit(TOPICS)
    return clf


class TestEmbeddingClassifier:
    def test_english_climbing_video(self, classifier: EmbeddingClassifier) -> None:
        video = Video(
            video_id="v1",
            title="Advanced bouldering technique for beginners",
            tags=["bouldering", "climbing", "rock climbing", "training"],
            channel_name="Lattice Training",
        )
        result = classifier.classify(video)
        assert result.top_topic == "escalada"

    def test_spanish_climbing_video(self, classifier: EmbeddingClassifier) -> None:
        video = Video(
            video_id="v2",
            title="Técnicas de escalada en roca para principiantes",
            tags=["escalada", "búlder", "entrenamiento"],
            channel_name="Escalada España",
        )
        result = classifier.classify(video)
        assert result.top_topic == "escalada"

    def test_investing_video(self, classifier: EmbeddingClassifier) -> None:
        video = Video(
            video_id="v3",
            title="How to build a long-term ETF portfolio",
            tags=["investing", "ETF", "index funds", "personal finance"],
            channel_name="Ben Felix",
        )
        result = classifier.classify(video)
        assert result.top_topic == "inversión"

    def test_cooking_video_spanish(self, classifier: EmbeddingClassifier) -> None:
        video = Video(
            video_id="v4",
            title="Cómo hacer paella valenciana perfecta",
            tags=["receta", "cocina", "paella", "arroz"],
            channel_name="Cocina con Carmen",
        )
        result = classifier.classify(video)
        assert result.top_topic == "comida"

    def test_scores_are_bounded(self, classifier: EmbeddingClassifier) -> None:
        video = Video(video_id="v5", title="Something random about life")
        result = classifier.classify(video)
        assert all(-1.0 <= score <= 1.0 for score in result.scores.values())

    def test_empty_video_returns_result(self, classifier: EmbeddingClassifier) -> None:
        video = Video(video_id="v6", title="")
        result = classifier.classify(video)
        # An empty video has no embeddings; top_score should be 0
        assert result.top_score == 0.0

    def test_top_n_returns_correct_count(self, classifier: EmbeddingClassifier) -> None:
        video = Video(
            video_id="v7",
            title="Outdoor photography while climbing",
            tags=["photography", "climbing", "outdoors"],
        )
        result = classifier.classify(video)
        top3 = result.top_n(3)
        assert len(top3) == 3
        scores = list(top3.values())
        assert scores == sorted(scores, reverse=True)

    def test_alternatives_are_sorted_descending(self, classifier: EmbeddingClassifier) -> None:
        video = Video(video_id="v8", title="Guitar lesson for beginners", tags=["guitar", "music"])
        result = classifier.classify(video)
        scores = list(result.top_n(5).values())
        assert scores == sorted(scores, reverse=True)


class TestMaxPoolSemantics:
    """Tests that verify per-field max pooling behaviour specifically."""

    def test_strong_title_not_diluted_by_irrelevant_description(
        self, classifier: EmbeddingClassifier
    ) -> None:
        """A perfect title match should not be dragged down by an unrelated description.

        Under the old weighted-average behaviour, the description "Random life
        thoughts about the weather…" would dilute the strong title signal. Under
        max pooling, the title alone defines the score for escalada.
        """
        # Title-only baseline
        title_only = Video(
            video_id="t1",
            title="Advanced bouldering technique for sport climbing",
        )
        # Same title but with an irrelevant description
        title_plus_noise = Video(
            video_id="t2",
            title="Advanced bouldering technique for sport climbing",
            description="Some general thoughts about my week and the weather lately. "
            "I went to the supermarket on Tuesday and bought bread.",
        )
        score_title_only = classifier.classify(title_only).scores["escalada"]
        score_with_noise = classifier.classify(title_plus_noise).scores["escalada"]

        # Max pool: noise can only push the score up (if it happens to match) or
        # leave it unchanged. It must NOT pull a strong title's score down.
        assert score_with_noise >= score_title_only - 1e-6

    def test_disabled_field_is_excluded(self) -> None:
        """Setting a field to False removes it from the max pool."""
        clf = EmbeddingClassifier(
            fields={"title": False, "tags": True, "channel": False, "description": False}
        )
        clf.fit(TOPICS)

        # Title is the only signal but title is disabled → no enabled fields → empty result
        video = Video(video_id="z1", title="Cooking paella valenciana recipe")
        result = clf.classify(video)
        assert result.scores == {}

    def test_description_alone_can_win(self) -> None:
        """If only description is enabled, the result must come from description."""
        clf = EmbeddingClassifier(
            fields={"title": False, "tags": False, "channel": False, "description": True}
        )
        clf.fit(TOPICS)

        video = Video(
            video_id="d1",
            title="Episode 42",  # uninformative
            description="A complete guide to investing in ETFs and building a long-term stock portfolio.",
        )
        result = clf.classify(video)
        assert result.top_topic == "inversión"

    def test_empty_video_returns_empty_scores(self, classifier: EmbeddingClassifier) -> None:
        video = Video(video_id="e1", title="")
        result = classifier.classify(video)
        assert result.scores == {}
        assert result.top_score == 0.0
