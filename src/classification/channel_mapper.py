import structlog

from classification.classifier import ClassificationResult


log = structlog.get_logger()


class ChannelMapper:
    """Adds a fixed score bonus to the AI result for known channels.

    Lookup is case-insensitive so "Lattice Training" and "lattice training"
    both match. Boosted scores are clipped to 1.0.
    """

    def __init__(self, mapping: dict[str, str], bonus: float) -> None:
        # Normalise keys to lowercase for case-insensitive lookup.
        # Store original name for logging.
        self._mapping: dict[str, tuple[str, str]] = {
            name.lower(): (name, topic)
            for name, topic in mapping.items()
        }
        self._bonus = bonus

    def lookup(self, channel_name: str) -> str | None:
        """Return the mapped topic for this channel, or None if not mapped."""
        entry = self._mapping.get(channel_name.lower())
        return entry[1] if entry else None

    def apply_boost(
        self, channel_name: str, result: ClassificationResult
    ) -> ClassificationResult:
        """Return a new ClassificationResult with the channel bonus applied.

        If the channel has no mapping, or the bonus is 0, the original result
        is returned unchanged.
        """
        topic = self.lookup(channel_name)
        if topic is None or self._bonus == 0.0:
            return result

        if topic not in result.scores:
            log.warning(
                "Channel mapped to unknown topic — boost skipped",
                channel=channel_name,
                topic=topic,
                hint="Add this topic to config/topics.yaml or fix config/channel_topics.yaml",
            )
            return result

        boosted = dict(result.scores)
        boosted[topic] = min(boosted[topic] + self._bonus, 1.0)
        log.debug(
            "Channel boost applied",
            channel=channel_name,
            topic=topic,
            before=round(result.scores[topic], 4),
            after=round(boosted[topic], 4),
        )
        return ClassificationResult(boosted)

    @property
    def size(self) -> int:
        """Number of channels with an assigned topic."""
        return len(self._mapping)
