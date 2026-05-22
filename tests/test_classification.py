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
