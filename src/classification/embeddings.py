import numpy as np
from sentence_transformers import SentenceTransformer

from classification.classifier import ClassificationResult
from domain.topic import Topic
from domain.video import Video


class EmbeddingClassifier:
    """Zero-shot classifier using per-field max-pool cosine similarity.

    Each video field (title, tags, channel, description) is embedded separately
    and scored against every topic. The final score per topic is the max
    similarity across all enabled fields. This prevents a strong title signal
    from being diluted by weaker description/channel signals.

    The `fields` dict controls which fields participate in the max pool.
    Setting a field to False excludes it entirely from scoring.
    """

    def __init__(
        self,
        model_name: str = "paraphrase-multilingual-MiniLM-L12-v2",
        fields: dict[str, bool] | None = None,
    ) -> None:
        self._model = SentenceTransformer(model_name)
        self._fields: dict[str, bool] = fields or {
            "title": True,
            "tags": True,
            "channel": True,
            "description": True,
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

        field_texts = self._collect_enabled_fields(video)
        if not field_texts:
            return ClassificationResult({})

        field_embs: np.ndarray = self._model.encode(
            field_texts, normalize_embeddings=True, show_progress_bar=False
        )

        scores: dict[str, float] = {}
        for topic_name, topic_emb in self._topic_embeddings.items():
            sims = [float(np.dot(fe, topic_emb)) for fe in field_embs]
            scores[topic_name] = max(sims)
        return ClassificationResult(scores)

    def _collect_enabled_fields(self, video: Video) -> list[str]:
        """Return non-empty field texts for enabled fields."""
        candidates = [
            (video.title, self._fields.get("title", True)),
            (" ".join(video.tags), self._fields.get("tags", True)),
            (video.channel_name, self._fields.get("channel", True)),
            (video.description[:500], self._fields.get("description", True)),
        ]
        return [text for text, enabled in candidates if enabled and text]
