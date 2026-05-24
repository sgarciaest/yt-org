from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class FieldsConfig:
    title: bool = True
    tags: bool = True
    channel: bool = True
    description: bool = True

    def as_dict(self) -> dict[str, bool]:
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
    model: str = "intfloat/multilingual-e5-base"
    fields: FieldsConfig = field(default_factory=FieldsConfig)
    thresholds: ThresholdsConfig = field(default_factory=ThresholdsConfig)
    top_n_alternatives: int = 3


@dataclass
class YouTubeConfig:
    client_secrets_file: str = "client_secrets.json"
    token_file: str = ".token.json"


@dataclass
class ChannelMappingConfig:
    config_file: str = "config/channel_topics.yaml"
    bonus: float = 0.25


@dataclass
class PlaylistsConfig:
    # Videos with action: keep or review (no topic) are added to WL/<fallback_name>.
    fallback_name: str = "general"


@dataclass
class AppConfig:
    youtube: YouTubeConfig = field(default_factory=YouTubeConfig)
    classification: ClassificationConfig = field(default_factory=ClassificationConfig)
    channel_mapping: ChannelMappingConfig = field(default_factory=ChannelMappingConfig)
    playlists: PlaylistsConfig = field(default_factory=PlaylistsConfig)


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

    f = cl.get("fields", {})
    cfg.classification.fields.title = bool(f.get("title", cfg.classification.fields.title))
    cfg.classification.fields.tags = bool(f.get("tags", cfg.classification.fields.tags))
    cfg.classification.fields.channel = bool(f.get("channel", cfg.classification.fields.channel))
    cfg.classification.fields.description = bool(
        f.get("description", cfg.classification.fields.description)
    )

    t = cl.get("thresholds", {})
    cfg.classification.thresholds.move = t.get("move", cfg.classification.thresholds.move)
    cfg.classification.thresholds.review = t.get(
        "review", cfg.classification.thresholds.review
    )

    cm = data.get("channel_mapping", {})
    cfg.channel_mapping.config_file = cm.get("config_file", cfg.channel_mapping.config_file)
    cfg.channel_mapping.bonus = cm.get("bonus", cfg.channel_mapping.bonus)

    pl = data.get("playlists", {})
    cfg.playlists.fallback_name = pl.get("fallback_name", cfg.playlists.fallback_name)

    return cfg


def load_channel_mapping(path: str | Path = "config/channel_topics.yaml") -> dict[str, str]:
    """Return {channel_name: topic} for all entries that have a non-null topic."""
    p = Path(path)
    if not p.exists():
        return {}
    with p.open() as f:
        data = yaml.safe_load(f) or {}
    result: dict[str, str] = {}
    for channel, details in data.get("channel_topics", {}).items():
        topic = details.get("topic") if isinstance(details, dict) else details
        if topic:
            result[channel] = topic
    return result


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
