from statistics import mean, pstdev
from typing import Any, Dict, List

from .schemas import PreviousGradedAnswer, StudentSubmission
from .text_utils import normalize_text


def fallback_similarity(a: str, b: str) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def compute_similarities(
    submission: StudentSubmission,
    previous_answers: List[PreviousGradedAnswer],
    top_k: int = 5
) -> List[Dict[str, Any]]:
    """
    Compare a submission with anonymised previously graded answers.

    If scikit-learn is available, TF-IDF cosine similarity is used.
    Otherwise, a deterministic fallback similarity is used.
    """
    if not previous_answers:
        return []

    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        corpus = [submission.answer] + [p.answer for p in previous_answers]
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform(corpus)
        similarities = cosine_similarity(matrix[0:1], matrix[1:]).flatten()

        scored = []
        for previous, sim in zip(previous_answers, similarities):
            scored.append({
                "copy_id": previous.copy_id,
                "similarity": round(float(sim), 3),
                "score": previous.score,
                "max_score": previous.max_score,
                "percentage": round(previous.score / previous.max_score * 100, 2),
                "grader_id": previous.grader_id,
                "lecturer_comment": previous.lecturer_comment,
            })

    except Exception:
        scored = []
        for previous in previous_answers:
            sim = fallback_similarity(submission.answer, previous.answer)
            scored.append({
                "copy_id": previous.copy_id,
                "similarity": round(sim, 3),
                "score": previous.score,
                "max_score": previous.max_score,
                "percentage": round(previous.score / previous.max_score * 100, 2),
                "grader_id": previous.grader_id,
                "lecturer_comment": previous.lecturer_comment,
            })

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:top_k]


def analyse_fairness_reference(
    indicative_percentage: float,
    similar_answers: List[Dict[str, Any]],
    warning_threshold: float = 15.0
) -> Dict[str, Any]:
    """
    Compare the indicative grade with similar previously graded answers.

    This does not decide whether the grade is correct.
    It flags possible consistency issues for lecturer review.
    """
    if not similar_answers:
        return {
            "available": False,
            "message": "No similar anonymised answers available for comparison."
        }

    percentages = [item["percentage"] for item in similar_answers]
    average_percentage = mean(percentages)
    deviation = indicative_percentage - average_percentage

    if len(percentages) > 1:
        spread = pstdev(percentages)
    else:
        spread = 0.0

    consistency_flag = abs(deviation) >= warning_threshold

    grader_groups: Dict[str, List[float]] = {}

    for item in similar_answers:
        grader_id = item.get("grader_id") or "unknown"
        grader_groups.setdefault(grader_id, []).append(item["percentage"])

    grader_summary = {
        grader: {
            "count": len(scores),
            "average_percentage": round(mean(scores), 2)
        }
        for grader, scores in grader_groups.items()
    }

    return {
        "available": True,
        "average_percentage_of_similar_answers": round(average_percentage, 2),
        "indicative_percentage": round(indicative_percentage, 2),
        "deviation_from_similar_average": round(deviation, 2),
        "spread_between_similar_answers": round(spread, 2),
        "consistency_flag": consistency_flag,
        "grader_summary": grader_summary,
        "message": (
            "Potential consistency issue flagged for lecturer review."
            if consistency_flag
            else "No major consistency issue detected from similar-answer comparison."
        ),
    }


class ComparisonEngine:
    def compare(
        self,
        submission: StudentSubmission,
        previous_answers: List[PreviousGradedAnswer],
        indicative_percentage: float,
        top_k: int = 5
    ) -> Dict[str, Any]:
        similar = compute_similarities(submission, previous_answers, top_k=top_k)
        fairness = analyse_fairness_reference(indicative_percentage, similar)

        return {
            "top_similar_answers": similar,
            "fairness_reference": fairness,
            "notice": (
                "Similar-answer comparison is provided only as an internal lecturer "
                "reference. It must not be used as an automatic grading decision."
            )
        }
