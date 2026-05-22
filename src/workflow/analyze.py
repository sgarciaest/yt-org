import structlog
from datetime import datetime, timezone

from classification.channel_mapper import ChannelMapper
from classification.classifier import Classifier
from classification.scoring import decide_action
from config import AppConfig
from domain.proposal import Proposal, VideoProposal
from domain.topic import Topic
from domain.video import Video


log = structlog.get_logger()


def run_analysis(
    videos: list[Video],
    topics: list[Topic],
    classifier: Classifier,
    config: AppConfig,
    channel_mapper: ChannelMapper | None = None,
) -> Proposal:
    thresholds = config.classification.thresholds
    top_n = config.classification.top_n_alternatives

    log.info("Fitting classifier on topics", count=len(topics))
    classifier.fit(topics)

    if channel_mapper is not None:
        log.info(
            "Channel mapper active",
            mapped_channels=channel_mapper.size,
            bonus=config.channel_mapping.bonus,
        )

    proposals: list[VideoProposal] = []

    for video in videos:
        ai_result = classifier.classify(video)
        ai_confidence = ai_result.top_score

        # Apply channel boost on top of AI scores
        channel_match: str | None = None
        if channel_mapper is not None:
            channel_match = channel_mapper.lookup(video.channel_name)
            final_result = channel_mapper.apply_boost(video.channel_name, ai_result)
        else:
            final_result = ai_result

        action = decide_action(final_result, thresholds.move, thresholds.review)
        predicted_topic = final_result.top_topic if action != "keep" else None
        confidence = final_result.top_score
        # Alternatives always show raw AI scores so the human reviewer sees what
        # the model thought independently of the channel boost.
        alternatives = ai_result.top_n(top_n)

        proposals.append(
            VideoProposal(
                video_id=video.video_id,
                title=video.title,
                predicted_topic=predicted_topic,
                confidence=confidence,
                alternatives=alternatives,
                action=action,
                channel_name=video.channel_name,
                description=video.description,
                tags=video.tags,
                channel_match=channel_match,
                ai_confidence=ai_confidence if channel_match is not None else None,
                playlist_item_id=video.playlist_item_id,
            )
        )
        log.info(
            "Classified",
            title=video.title[:60],
            topic=predicted_topic,
            confidence=round(confidence, 3),
            channel_boost=channel_match,
            action=action,
        )

    return Proposal(
        generated_at=datetime.now(timezone.utc),
        move_threshold=thresholds.move,
        review_threshold=thresholds.review,
        videos=proposals,
    )
