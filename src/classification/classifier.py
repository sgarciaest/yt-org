from typing import Protocol

from domain.topic import Topic
from domain.video import Video


class ClassificationResult:
    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores

    @property
    def top_topic(self) -> str | None:
        if not self.scores:
            return None
        return max(self.scores, key=self.scores.__getitem__)

    @property
    def top_score(self) -> float:
        if not self.scores:
            return 0.0
        return max(self.scores.values())

    def top_n(self, n: int) -> dict[str, float]:
        sorted_scores = sorted(self.scores.items(), key=lambda x: x[1], reverse=True)
        return dict(sorted_scores[:n])


class Classifier(Protocol):
    def fit(self, topics: list[Topic]) -> None: ...
    def classify(self, video: Video) -> ClassificationResult: ...
