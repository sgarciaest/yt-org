import pytest

from classification.classifier import ClassificationResult
from classification.scoring import decide_action


MOVE = 0.82
REVIEW = 0.60


@pytest.mark.parametrize(
    "scores, expected",
    [
        ({"escalada": 0.90, "fotografía": 0.30}, "move"),
        ({"escalada": MOVE, "fotografía": 0.20}, "move"),       # exact threshold
        ({"inversión": 0.75, "música": 0.20}, "review"),
        ({"inversión": REVIEW, "música": 0.10}, "review"),      # exact threshold
        ({"comida": 0.45, "música": 0.30}, "keep"),
        ({}, "keep"),                                            # empty scores
    ],
)
def test_decide_action(scores: dict[str, float], expected: str) -> None:
    result = ClassificationResult(scores)
    assert decide_action(result, MOVE, REVIEW) == expected
