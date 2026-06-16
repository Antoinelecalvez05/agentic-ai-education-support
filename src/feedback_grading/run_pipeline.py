import argparse
import json
from pathlib import Path

from .pipeline import FeedbackGradingPipeline
from .schemas import PreviousGradedAnswer, Rubric, StudentSubmission


def load_json(path: Path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the feedback and grading-support pipeline."
    )

    parser.add_argument("--rubric", required=True, help="Path to rubric JSON file")
    parser.add_argument("--submission", required=True, help="Path to student submission JSON file")
    parser.add_argument("--previous", required=True, help="Path to previous anonymised answers JSON file")
    parser.add_argument("--out", default="src/feedback_grading/outputs", help="Output directory")

    args = parser.parse_args()

    rubric_data = load_json(Path(args.rubric))
    submission_data = load_json(Path(args.submission))
    previous_data = load_json(Path(args.previous))

    rubric = Rubric.from_dict(rubric_data)
    submission = StudentSubmission.from_dict(submission_data)
    previous_answers = [
        PreviousGradedAnswer.from_dict(item)
        for item in previous_data.get("previous_answers", [])
    ]

    pipeline = FeedbackGradingPipeline()

    output = pipeline.run(
        rubric=rubric,
        submission=submission,
        previous_answers=previous_answers,
        output_dir=Path(args.out),
    )

    print("Feedback and grading pipeline completed.")
    print(f"JSON result: {output['json_result_path']}")
    print(f"Markdown report: {output['markdown_report_path']}")
    print(f"Audit log: {output['audit_log_path']}")


if __name__ == "__main__":
    main()
