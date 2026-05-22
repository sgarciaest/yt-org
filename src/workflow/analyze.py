import structlog
from datetime import datetime, timezone

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
) -> Proposal:
    thresholds = config.classification.thresholds
    top_n = config.classification.top_n_alternatives

    log.info("Fitting classifier on topics", count=len(topics))
    classifier.fit(topics)

    proposals: list[VideoProposal] = []

    for video in videos:
        result = classifier.classify(video)

        action = decide_action(result, thresholds.move, thresholds.review)
        predicted_topic = result.top_topic if action != "keep" else None
        confidence = result.top_score
        alternatives = result.top_n(top_n)

        proposals.append(
            VideoProposal(
                video_id=video.video_id,
                title=video.title,
                predicted_topic=predicted_topic,
                confidence=confidence,
                alternatives=alternatives,
                action=action,
                playlist_item_id=video.playlist_item_id,
            )
        )
        log.info(
            "Classified",
            title=video.title[:60],
            topic=predicted_topic,
            confidence=round(confidence, 3),
            action=action,
        )

    return Proposal(
        generated_at=datetime.now(timezone.utc),
        move_threshold=thresholds.move,
        review_threshold=thresholds.review,
        videos=proposals,
    )
