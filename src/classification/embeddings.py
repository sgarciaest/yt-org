import numpy as np
from sentence_transformers import SentenceTransformer

from classification.classifier import ClassificationResult
from domain.topic import Topic
from domain.video import Video


class EmbeddingClassifier:
    """Zero-shot classifier using sentence embeddings and cosine similarity."""

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        weights: dict[str, float] | None = None,
    ) -> None:
        self._model = SentenceTransformer(model_name)
        self._weights: dict[str, float] = weights or {
            "title": 3.0,
            "tags": 2.0,
            "channel": 1.5,
            "description": 1.0,
        }
        self._topic_embeddings: dict[str, np.ndarray] = {}

    def fit(self, topics: list[Topic]) -> None:
        topic_texts = [f"{t.name}: {t.description}" for t in topics]
        embeddings: np.ndarray = self._model.encode(
            topic_texts, normalize_embeddings=True, show_progress_bar=False
        )
        for topic, embedding in zip(topics, embeddings):
            self._topic_embeddings[topic.name] = embedding

    def classify(self, video: Video) -> ClassificationResult:
        if not self._topic_embeddings:
            raise RuntimeError("Classifier not fitted. Call fit() before classify().")

        video_embedding = self._build_video_embedding(video)
        if video_embedding is None:
            return ClassificationResult({})

        scores: dict[str, float] = {
            name: float(np.dot(video_embedding, emb))
            for name, emb in self._topic_embeddings.items()
        }
        return ClassificationResult(scores)

    def _build_video_embedding(self, video: Video) -> np.ndarray | None:
        parts: list[tuple[str, float]] = []

        if video.title:
            parts.append((video.title, self._weights.get("title", 3.0)))
        if video.tags:
            parts.append((" ".join(video.tags), self._weights.get("tags", 2.0)))
        if video.channel_name:
            parts.append((video.channel_name, self._weights.get("channel", 1.5)))
        if video.description:
            parts.append((video.description[:500], self._weights.get("description", 1.0)))

        if not parts:
            return None

        texts = [text for text, _ in parts]
        raw_weights = np.array([w for _, w in parts])
        raw_weights = raw_weights / raw_weights.sum()

        embeddings: np.ndarray = self._model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False
        )
        weighted = np.average(embeddings, axis=0, weights=raw_weights)

        norm = float(np.linalg.norm(weighted))
        if norm == 0.0:
            return None
        return weighted / norm
