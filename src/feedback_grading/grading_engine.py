from typing import Any, Dict, List

from .schemas import Criterion, Rubric, StudentSubmission
from .text_utils import evidence_match


def round_to_half(value: float) -> float:
    return round(value * 2) / 2


class GradingEngine:
    """
    Rubric-grounded indicative grading engine.

    This engine does not make final academic decisions.
    It produces structured evidence and indicative scoring for lecturer review.
    """

    def evaluate_criterion(
        self,
        submission: StudentSubmission,
        criterion: Criterion
    ) -> Dict[str, Any]:
        element_results = []

        for element in criterion.expected_elements:
            confidence = evidence_match(submission.answer, element)

            if confidence >= 0.75:
                status = "found"
            elif confidence >= 0.4:
                status = "partial"
            else:
                status = "missing"

            element_results.append({
                "expected_element": element,
                "match_confidence": round(confidence, 3),
                "status": status,
            })

        found_weight = 0.0

        for item in element_results:
            if item["status"] == "found":
                found_weight += 1.0
            elif item["status"] == "partial":
                found_weight += 0.5

        if criterion.expected_elements:
            coverage = found_weight / len(criterion.expected_elements)
        else:
            coverage = 0.0

        raw_score = criterion.max_points * coverage
        indicative_score = min(criterion.max_points, round_to_half(raw_score))

        missing_elements = [
            item["expected_element"]
            for item in element_results
            if item["status"] == "missing"
        ]

        partial_elements = [
            item["expected_element"]
            for item in element_results
            if item["status"] == "partial"
        ]

        found_elements = [
            item["expected_element"]
            for item in element_results
            if item["status"] == "found"
        ]

        if indicative_score == criterion.max_points:
            feedback_type = "strong"
        elif indicative_score == 0:
            feedback_type = "weak"
        else:
            feedback_type = "partial"

        return {
            "criterion_id": criterion.id,
            "title": criterion.title,
            "max_points": criterion.max_points,
            "indicative_score": indicative_score,
            "coverage": round(coverage, 3),
            "feedback_type": feedback_type,
            "found_elements": found_elements,
            "partial_elements": partial_elements,
            "missing_elements": missing_elements,
            "element_evidence": element_results,
            "feedback_guidance": criterion.feedback_guidance,
        }

    def evaluate_submission(
        self,
        submission: StudentSubmission,
        rubric: Rubric
    ) -> Dict[str, Any]:
        criterion_results: List[Dict[str, Any]] = []

        for criterion in rubric.criteria:
            result = self.evaluate_criterion(submission, criterion)
            criterion_results.append(result)

        total_score = sum(item["indicative_score"] for item in criterion_results)
        percentage = (total_score / rubric.total_points * 100) if rubric.total_points else 0

        return {
            "assignment_id": rubric.assignment_id,
            "student_id": submission.student_id,
            "question": rubric.question,
            "indicative_total_score": round(total_score, 2),
            "total_possible": round(rubric.total_points, 2),
            "indicative_percentage": round(percentage, 2),
            "criteria": criterion_results,
            "important_notice": (
                "This is an indicative score generated for lecturer review only. "
                "It is not a final grade."
            ),
        }

