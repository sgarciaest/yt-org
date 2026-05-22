from classification.classifier import ClassificationResult
from domain.proposal import Action


def decide_action(
    result: ClassificationResult,
    move_threshold: float,
    review_threshold: float,
) -> Action:
    score = result.top_score
    if score >= move_threshold:
        return "move"
    if score >= review_threshold:
        return "review"
    return "keep"
