from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class SchemaValidationError(Exception):
    """Raised when an input schema is invalid."""


@dataclass
class Criterion:
    id: str
    title: str
    max_points: float
    expected_elements: List[str]
    common_errors: List[str] = field(default_factory=list)
    feedback_guidance: str = ""
    evidence_required: bool = True

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Criterion":
        required = ["id", "title", "max_points", "expected_elements"]
        for key in required:
            if key not in data:
                raise SchemaValidationError(f"Criterion missing required field: {key}")

        if not isinstance(data["expected_elements"], list):
            raise SchemaValidationError("expected_elements must be a list")

        return Criterion(
            id=str(data["id"]),
            title=str(data["title"]),
            max_points=float(data["max_points"]),
            expected_elements=[str(x) for x in data["expected_elements"]],
            common_errors=[str(x) for x in data.get("common_errors", [])],
            feedback_guidance=str(data.get("feedback_guidance", "")),
            evidence_required=bool(data.get("evidence_required", True)),
        )


@dataclass
class Rubric:
    assignment_id: str
    question: str
    total_points: float
    criteria: List[Criterion]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Rubric":
        required = ["assignment_id", "question", "criteria"]
        for key in required:
            if key not in data:
                raise SchemaValidationError(f"Rubric missing required field: {key}")

        criteria = [Criterion.from_dict(item) for item in data["criteria"]]
        total_points = sum(c.max_points for c in criteria)

        return Rubric(
            assignment_id=str(data["assignment_id"]),
            question=str(data["question"]),
            total_points=total_points,
            criteria=criteria,
        )


@dataclass
class StudentSubmission:
    student_id: str
    answer: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "StudentSubmission":
        if "student_id" not in data:
            raise SchemaValidationError("Submission missing student_id")
        if "answer" not in data:
            raise SchemaValidationError("Submission missing answer")

        return StudentSubmission(
            student_id=str(data["student_id"]),
            answer=str(data["answer"]),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass
class PreviousGradedAnswer:
    copy_id: str
    answer: str
    score: float
    max_score: float
    grader_id: Optional[str] = None
    lecturer_comment: str = ""

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PreviousGradedAnswer":
        required = ["copy_id", "answer", "score", "max_score"]
        for key in required:
            if key not in data:
                raise SchemaValidationError(f"Previous answer missing required field: {key}")

        return PreviousGradedAnswer(
            copy_id=str(data["copy_id"]),
            answer=str(data["answer"]),
            score=float(data["score"]),
            max_score=float(data["max_score"]),
            grader_id=str(data["grader_id"]) if data.get("grader_id") is not None else None,
            lecturer_comment=str(data.get("lecturer_comment", "")),
        )

