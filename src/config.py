from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class WeightsConfig:
    title: float = 3.0
    tags: float = 2.0
    channel: float = 1.5
    description: float = 1.0

    def as_dict(self) -> dict[str, float]:
        return {
            "title": self.title,
            "tags": self.tags,
            "channel": self.channel,
            "description": self.description,
        }


@dataclass
class ThresholdsConfig:
    move: float = 0.82
    review: float = 0.60


@dataclass
class ClassificationConfig:
    model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    weights: WeightsConfig = field(default_factory=WeightsConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    top_n_alternatives: int = 3


@dataclass
class YouTubeConfig:
    client_secrets_file: str = "client_secrets.json"
    token_file: str = ".token.json"


@dataclass
class AppConfig:
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)


def load_config(path: str | Path = "config/settings.yaml") -> AppConfig:
    p = Path(path)
    if not p.exists():
        return AppConfig()

    with p.open() as f:
        data = yaml.safe_load(f) or {}

    cfg = AppConfig()

    yt = data.get("youtube", {})
    cfg.youtube.client_secrets_file = yt.get(
        "client_secrets_file", cfg.youtube.client_secrets_file
    )
    cfg.youtube.token_file = yt.get("token_file", cfg.youtube.token_file)

    cl = data.get("classification", {})
    cfg.classification.model = cl.get("model", cfg.classification.model)
    cfg.classification.top_n_alternatives = cl.get(
        "top_n_alternatives", cfg.classification.top_n_alternatives
    )

    w = cl.get("weights", {})
    cfg.classification.weights.title = w.get("title", cfg.classification.weights.title)
    cfg.classification.weights.tags = w.get("tags", cfg.classification.weights.tags)
    cfg.classification.weights.channel = w.get("channel", cfg.classification.weights.channel)
    cfg.classification.weights.description = w.get(
        "description", cfg.classification.weights.description
    )

    t = cl.get("thresholds", {})
    cfg.classification.thresholds.move = t.get("move", cfg.classification.thresholds.move)
    cfg.classification.thresholds.review = t.get(
        "review", cfg.classification.thresholds.review
    )

    return cfg


def load_topics_config(path: str | Path = "config/topics.yaml") -> dict[str, str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Topics config not found: {path}")

    with p.open() as f:
        data = yaml.safe_load(f) or {}

    return {
        name: details.get("description", name)
        for name, details in data.get("topics", {}).items()
    }
