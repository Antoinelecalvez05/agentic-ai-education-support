from typing import Any, Dict


class ReportGenerator:
    def generate_markdown(
        self,
        grading_result: Dict[str, Any],
        comparison_result: Dict[str, Any]
    ) -> str:
        lines = []

        lines.append("# Indicative Feedback and Grading Report")
        lines.append("")
        lines.append("## Important Notice")
        lines.append("")
        lines.append(
            "This report is generated as a lecturer-support tool. "
            "It is not a final academic decision. A lecturer must review, edit, "
            "and validate any feedback or indicative score before use."
        )
        lines.append("")

        lines.append("## Summary")
        lines.append("")
        lines.append(f"- Assignment ID: `{grading_result['assignment_id']}`")
        lines.append(f"- Student ID: `{grading_result['student_id']}`")
        lines.append(
            f"- Indicative score: **{grading_result['indicative_total_score']} / "
            f"{grading_result['total_possible']}**"
        )
        lines.append(f"- Indicative percentage: **{grading_result['indicative_percentage']}%**")
        lines.append("")

        lines.append("## Criterion-by-Criterion Evaluation")
        lines.append("")

        for criterion in grading_result["criteria"]:
            lines.append(f"### {criterion['title']}")
            lines.append("")
            lines.append(
                f"- Indicative score: **{criterion['indicative_score']} / "
                f"{criterion['max_points']}**"
            )
            lines.append(f"- Coverage estimate: `{criterion['coverage']}`")
            lines.append("")

            if criterion["found_elements"]:
                lines.append("**Elements found:**")
                for item in criterion["found_elements"]:
                    lines.append(f"- {item}")
                lines.append("")

            if criterion["partial_elements"]:
                lines.append("**Partially addressed elements:**")
                for item in criterion["partial_elements"]:
                    lines.append(f"- {item}")
                lines.append("")

            if criterion["missing_elements"]:
                lines.append("**Missing or unclear elements:**")
                for item in criterion["missing_elements"]:
                    lines.append(f"- {item}")
                lines.append("")

            if criterion.get("feedback_guidance"):
                lines.append("**Lecturer feedback guidance:**")
                lines.append("")
                lines.append(criterion["feedback_guidance"])
                lines.append("")

        lines.append("## Similar-Answer Comparison")
        lines.append("")

        similar = comparison_result.get("top_similar_answers", [])

        if similar:
            lines.append("Top similar anonymised previously graded answers:")
            lines.append("")
            for item in similar:
                lines.append(
                    f"- `{item['copy_id']}` | similarity: `{item['similarity']}` | "
                    f"score: `{item['score']} / {item['max_score']}` | "
                    f"grader: `{item.get('grader_id')}`"
                )
            lines.append("")
        else:
            lines.append("No similar anonymised answers were available.")
            lines.append("")

        fairness = comparison_result.get("fairness_reference", {})
        lines.append("## Fairness / Consistency Reference")
        lines.append("")

        if fairness.get("available"):
            lines.append(
                f"- Average percentage of similar answers: "
                f"**{fairness['average_percentage_of_similar_answers']}%**"
            )
            lines.append(
                f"- Current indicative percentage: "
                f"**{fairness['indicative_percentage']}%**"
            )
            lines.append(
                f"- Deviation from similar-answer average: "
                f"**{fairness['deviation_from_similar_average']} points**"
            )
            lines.append(
                f"- Consistency flag: **{fairness['consistency_flag']}**"
            )
            lines.append("")
            lines.append(fairness["message"])
        else:
            lines.append(fairness.get("message", "No fairness reference available."))

        lines.append("")
        lines.append("## Lecturer Review Required")
        lines.append("")
        lines.append(
            "Before being shared with a student, this report should be reviewed "
            "by a lecturer. The lecturer may accept, reject, edit, or reinterpret "
            "any part of the generated feedback."
        )

        return "\n".join(lines)
