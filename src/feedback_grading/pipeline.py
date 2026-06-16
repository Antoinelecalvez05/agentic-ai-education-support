import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from .comparison_engine import ComparisonEngine
from .grading_engine import GradingEngine
from .report_generator import ReportGenerator
from .schemas import PreviousGradedAnswer, Rubric, StudentSubmission


class FeedbackGradingPipeline:
    """
    Full feedback and grading-support pipeline.

    This class connects:
    - rubric validation
    - criterion-by-criterion evaluation
    - indicative grading
    - similar-copy comparison
    - fairness reference generation
    - lecturer-review report generation
    """

    def __init__(self) -> None:
        self.grading_engine = GradingEngine()
        self.comparison_engine = ComparisonEngine()
        self.report_generator = ReportGenerator()

    def run(
        self,
        rubric: Rubric,
        submission: StudentSubmission,
        previous_answers: List[PreviousGradedAnswer],
        output_dir: Path
    ) -> Dict[str, Any]:
        output_dir.mkdir(parents=True, exist_ok=True)

        grading_result = self.grading_engine.evaluate_submission(submission, rubric)

        comparison_result = self.comparison_engine.compare(
            submission=submission,
            previous_answers=previous_answers,
            indicative_percentage=grading_result["indicative_percentage"],
            top_k=5,
        )

        markdown_report = self.report_generator.generate_markdown(
            grading_result=grading_result,
            comparison_result=comparison_result,
        )

        result = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "rubric": {
                "assignment_id": rubric.assignment_id,
                "question": rubric.question,
                "total_points": rubric.total_points,
            },
            "grading_result": grading_result,
            "comparison_result": comparison_result,
            "human_review_required": True,
            "final_decision": "Lecturer review required before use.",
        }

        json_path = output_dir / "feedback_grading_result.json"
        report_path = output_dir / "feedback_grading_report.md"
        audit_path = output_dir / "audit_log.json"

        with json_path.open("w", encoding="utf-8") as file:
            json.dump(result, file, indent=2, ensure_ascii=False)

        with report_path.open("w", encoding="utf-8") as file:
            file.write(markdown_report)

        audit_log = {
            "generated_at": result["generated_at"],
            "student_id": submission.student_id,
            "assignment_id": rubric.assignment_id,
            "human_review_required": True,
            "outputs": {
                "json_result": str(json_path),
                "markdown_report": str(report_path),
            },
            "safety_notes": [
                "Indicative score only",
                "Lecturer review required",
                "No automatic final grading",
                "Comparison is internal reference only"
            ],
        }

        with audit_path.open("w", encoding="utf-8") as file:
            json.dump(audit_log, file, indent=2, ensure_ascii=False)

        return {
            "json_result_path": str(json_path),
            "markdown_report_path": str(report_path),
            "audit_log_path": str(audit_path),
            "result": result,
        }
