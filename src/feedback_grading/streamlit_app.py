"""
Professional Streamlit interface for the feedback/grading support system.

Run from the repository root:

    streamlit run src/feedback_grading/streamlit_app.py

Repository expected root:

    ~/GitHub/agentic-ai-education-support

Important principles:
- This is a lecturer-support tool.
- It does not make final academic grading decisions.
- AI-generated rubrics must be reviewed and validated by a lecturer.
- Scores are indicative only.
- Student data should be anonymised before processing.
"""

from __future__ import annotations

import dataclasses
import inspect
import io
import json
import re
import subprocess
import sys
import traceback
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

import pandas as pd
import streamlit as st


# ---------------------------------------------------------------------
# Import backend modules robustly
# ---------------------------------------------------------------------

CURRENT_FILE = Path(__file__).resolve()
PROJECT_ROOT = CURRENT_FILE.parents[2]
OUTPUT_ROOT = CURRENT_FILE.parent / "outputs" / "streamlit_batch"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BACKEND_IMPORT_ERROR: Optional[Exception] = None

try:
    from src.feedback_grading.rubric_ai_parser import RubricAIParser
    from src.feedback_grading.schemas import Rubric, StudentSubmission, PreviousGradedAnswer
    from src.feedback_grading.pipeline import FeedbackGradingPipeline

    try:
        from src.feedback_grading.report_generator import ReportGenerator
    except Exception:
        ReportGenerator = None

except Exception as exc:  # pragma: no cover - shown in Streamlit UI
    BACKEND_IMPORT_ERROR = exc
    RubricAIParser = None
    Rubric = None
    StudentSubmission = None
    PreviousGradedAnswer = None
    FeedbackGradingPipeline = None
    ReportGenerator = None


# ---------------------------------------------------------------------
# Streamlit page setup
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Feedback & Grading Support",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Important UI note:
# No custom HTML, CSS, JavaScript, or components are used for layout.
# The interface uses native Streamlit components only.


# ---------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------

def init_session_state() -> None:
    defaults = {
        "rubric_data": None,
        "rubric_validated": False,
        "previous_answers_data": [],
        "submissions_data": [],
        "batch_results": [],
        "summary_rows": [],
        "reports": {},
        "last_run_dir": None,
        "last_error": None,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_session_state()


# ---------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------

def require_backend() -> None:
    if BACKEND_IMPORT_ERROR is not None:
        st.error("The feedback/grading backend could not be imported.")
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(BACKEND_IMPORT_ERROR)))
        st.stop()


def safe_filename(value: str) -> str:
    value = str(value or "unknown").strip()
    value = re.sub(r"[^a-zA-Z0-9._-]+", "_", value)
    return value[:80] or "unknown"


def now_run_id() -> str:
    return datetime.now().strftime("batch_%Y%m%d_%H%M%S")


def to_plain_data(value: Any) -> Any:
    """
    Convert dataclasses / Pydantic models / simple objects into JSON-like data.
    """
    if value is None:
        return None

    if isinstance(value, (str, int, float, bool)):
        return value

    if isinstance(value, Mapping):
        return {str(k): to_plain_data(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_plain_data(v) for v in value]

    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)

    if hasattr(value, "model_dump"):
        return value.model_dump()

    if hasattr(value, "dict"):
        return value.dict()

    if hasattr(value, "__dict__"):
        return {
            k: to_plain_data(v)
            for k, v in vars(value).items()
            if not str(k).startswith("_")
        }

    return value


def json_dumps(data: Any, indent: int = 2) -> str:
    return json.dumps(to_plain_data(data), ensure_ascii=False, indent=indent, default=str)


def parse_json_text(text: str) -> Any:
    """
    Parses plain JSON. Also tolerates JSON inside Markdown code fences.
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text.strip(), flags=re.IGNORECASE).strip()
        text = re.sub(r"```$", "", text.strip()).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        first = text.find("{")
        last = text.rfind("}")
        if first >= 0 and last > first:
            return json.loads(text[first:last + 1])
        raise


def load_uploaded_json(uploaded_file) -> Any:
    raw = uploaded_file.read().decode("utf-8")
    return parse_json_text(raw)


def load_uploaded_text(uploaded_file) -> str:
    return uploaded_file.read().decode("utf-8")


def ensure_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]

    if isinstance(value, tuple):
        return [str(v).strip() for v in value if str(v).strip()]

    if isinstance(value, str):
        lines = [line.strip() for line in value.splitlines()]
        return [line for line in lines if line]

    return [str(value).strip()]


def list_to_text(value: Any) -> str:
    return "\n".join(ensure_list(value))


def text_to_list(value: str) -> List[str]:
    return [line.strip() for line in str(value).splitlines() if line.strip()]


def first_value(data: Mapping[str, Any], paths: List[List[str]], default: Any = None) -> Any:
    for path in paths:
        current: Any = data
        found = True

        for key in path:
            if isinstance(current, Mapping) and key in current:
                current = current[key]
            else:
                found = False
                break

        if found and current is not None:
            return current

    return default


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def build_schema_instance(schema_cls: Any, data: Dict[str, Any]) -> Any:
    """
    Build an instance of a backend schema class without assuming whether it is:
    - a dataclass
    - a Pydantic model
    - a regular Python class with __init__
    - a class exposing from_dict/model_validate/parse_obj
    """
    if schema_cls is None:
        return data

    plain = to_plain_data(data)

    for method_name in ("model_validate", "from_dict", "parse_obj"):
        method = getattr(schema_cls, method_name, None)
        if callable(method):
            try:
                return method(plain)
            except Exception:
                pass

    try:
        return schema_cls(**plain)
    except Exception as full_error:
        try:
            signature = inspect.signature(schema_cls)
            accepted = {
                key: value
                for key, value in plain.items()
                if key in signature.parameters
            }
            return schema_cls(**accepted)
        except Exception as filtered_error:
            raise ValueError(
                f"Could not build {getattr(schema_cls, '__name__', schema_cls)} "
                f"from provided data.\n\n"
                f"Full error: {full_error}\n"
                f"Filtered error: {filtered_error}"
            ) from filtered_error


# ---------------------------------------------------------------------
# Rubric helpers
# ---------------------------------------------------------------------

def normalize_criterion(raw: Mapping[str, Any], index: int) -> Dict[str, Any]:
    item = dict(raw)

    criterion_id = (
        item.get("criterion_id")
        or item.get("id")
        or item.get("code")
        or f"C{index + 1}"
    )

    name = (
        item.get("name")
        or item.get("title")
        or item.get("criterion")
        or item.get("label")
        or criterion_id
    )

    description = item.get("description") or item.get("details") or ""

    max_points = (
        item.get("max_points")
        if item.get("max_points") is not None
        else item.get("points", item.get("max_score", 0))
    )

    expected_elements = (
        item.get("expected_elements")
        or item.get("expected")
        or item.get("key_points")
        or item.get("marking_points")
        or []
    )

    common_errors = (
        item.get("common_errors")
        or item.get("errors")
        or item.get("typical_errors")
        or []
    )

    feedback_guidance = (
        item.get("feedback_guidance")
        or item.get("feedback")
        or item.get("guidance")
        or ""
    )

    item["criterion_id"] = str(criterion_id)
    item["name"] = str(name)
    item["description"] = str(description)
    item["max_points"] = as_float(max_points, 0.0) or 0.0
    item["expected_elements"] = ensure_list(expected_elements)
    item["common_errors"] = ensure_list(common_errors)
    item["feedback_guidance"] = str(feedback_guidance)

    return item


def normalize_rubric_data(raw: Any) -> Dict[str, Any]:
    """
    Normalise AI or JSON rubric output into the expected editable structure.
    Keeps extra fields if present.
    """
    raw = to_plain_data(raw)

    if isinstance(raw, str):
        raw = parse_json_text(raw)

    if not isinstance(raw, Mapping):
        raise ValueError("Rubric must be a JSON object/dictionary.")

    if "rubric" in raw and isinstance(raw["rubric"], Mapping):
        raw = raw["rubric"]

    data = dict(raw)

    criteria = (
        data.get("criteria")
        or data.get("marking_criteria")
        or data.get("rubric_criteria")
        or []
    )

    if not isinstance(criteria, list):
        raise ValueError("Rubric criteria must be a list.")

    data["assignment_id"] = str(
        data.get("assignment_id")
        or data.get("assignment")
        or data.get("assessment_id")
        or "assignment_001"
    )

    data["question"] = str(
        data.get("question")
        or data.get("task")
        or data.get("prompt")
        or ""
    )

    data["criteria"] = [
        normalize_criterion(criterion, index)
        for index, criterion in enumerate(criteria)
        if isinstance(criterion, Mapping)
    ]

    return data


def parse_rubric_with_ai(raw_text: str) -> Dict[str, Any]:
    """
    Uses the existing RubricAIParser backend.

    This function intentionally does not implement AI extraction logic itself.
    It only adapts possible parser method names/signatures.
    """
    require_backend()

    if not raw_text.strip():
        raise ValueError("No marking scheme text was provided.")

    parser = RubricAIParser()

    candidate_methods = [
        "parse",
        "parse_text",
        "parse_marking_scheme",
        "generate_rubric",
        "generate",
        "run",
        "convert",
    ]

    errors: List[str] = []

    for method_name in candidate_methods:
        method = getattr(parser, method_name, None)
        if not callable(method):
            continue

        call_attempts = [
            lambda: method(raw_text),
            lambda: method(text=raw_text),
            lambda: method(raw_text=raw_text),
            lambda: method(marking_scheme_text=raw_text),
            lambda: method(marking_scheme=raw_text),
        ]

        for attempt in call_attempts:
            try:
                result = attempt()
                return normalize_rubric_data(result)
            except TypeError as exc:
                errors.append(f"{method_name}: {exc}")
                continue
            except Exception as exc:
                errors.append(f"{method_name}: {exc}")
                break

    if callable(parser):
        try:
            return normalize_rubric_data(parser(raw_text))
        except Exception as exc:
            errors.append(f"callable parser: {exc}")

    raise RuntimeError(
        "Could not parse the marking scheme with RubricAIParser.\n\n"
        + "\n".join(errors[-8:])
    )


def validate_rubric_with_backend(rubric_data: Dict[str, Any]) -> Any:
    require_backend()
    return build_schema_instance(Rubric, rubric_data)


def rubric_total_points(rubric_data: Optional[Dict[str, Any]]) -> float:
    if not rubric_data:
        return 0.0

    total = 0.0
    for criterion in rubric_data.get("criteria", []):
        total += as_float(criterion.get("max_points"), 0.0) or 0.0

    return total


# ---------------------------------------------------------------------
# Previous answers / submissions helpers
# ---------------------------------------------------------------------

def validate_previous_answer(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    required = ["copy_id", "answer", "score", "max_score", "grader_id"]

    missing = [field for field in required if item.get(field) in (None, "")]
    if missing:
        raise ValueError(
            f"Previous answer #{index + 1} is missing required fields: "
            + ", ".join(missing)
        )

    score = as_float(item.get("score"))
    max_score = as_float(item.get("max_score"))

    if score is None or max_score is None:
        raise ValueError(f"Previous answer #{index + 1} has invalid score values.")

    return {
        "copy_id": str(item.get("copy_id")),
        "answer": str(item.get("answer")),
        "score": score,
        "max_score": max_score,
        "grader_id": str(item.get("grader_id")),
        "lecturer_comment": str(item.get("lecturer_comment", "")),
    }


def validate_previous_payload(payload: Any) -> List[Dict[str, Any]]:
    payload = to_plain_data(payload)

    if isinstance(payload, Mapping) and "previous_answers" in payload:
        items = payload["previous_answers"]
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError("Expected JSON format: {'previous_answers': [ ... ]}")

    if not isinstance(items, list):
        raise ValueError("'previous_answers' must be a list.")

    return [
        validate_previous_answer(item, index)
        for index, item in enumerate(items)
        if isinstance(item, Mapping)
    ]


def validate_submission(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    required = ["student_id", "answer"]

    missing = [field for field in required if item.get(field) in (None, "")]
    if missing:
        raise ValueError(
            f"Submission #{index + 1} is missing required fields: "
            + ", ".join(missing)
        )

    metadata = item.get("metadata") or {}
    if not isinstance(metadata, Mapping):
        raise ValueError(f"Submission #{index + 1} metadata must be a JSON object.")

    return {
        "student_id": str(item.get("student_id")),
        "answer": str(item.get("answer")),
        "metadata": dict(metadata),
    }


def validate_submissions_payload(payload: Any) -> List[Dict[str, Any]]:
    payload = to_plain_data(payload)

    if isinstance(payload, Mapping) and "submissions" in payload:
        items = payload["submissions"]
    elif isinstance(payload, list):
        items = payload
    else:
        raise ValueError("Expected JSON format: {'submissions': [ ... ]}")

    if not isinstance(items, list):
        raise ValueError("'submissions' must be a list.")

    return [
        validate_submission(item, index)
        for index, item in enumerate(items)
        if isinstance(item, Mapping)
    ]


def previous_answers_dataframe() -> pd.DataFrame:
    rows = []
    for item in st.session_state.previous_answers_data:
        rows.append(
            {
                "copy_id": item.get("copy_id"),
                "score": item.get("score"),
                "max_score": item.get("max_score"),
                "grader_id": item.get("grader_id"),
                "lecturer_comment": item.get("lecturer_comment"),
                "answer_preview": str(item.get("answer", ""))[:160],
            }
        )
    return pd.DataFrame(rows)


def submissions_dataframe() -> pd.DataFrame:
    rows = []
    for item in st.session_state.submissions_data:
        rows.append(
            {
                "student_id": item.get("student_id"),
                "metadata": json_dumps(item.get("metadata", {}), indent=0),
                "answer_preview": str(item.get("answer", ""))[:180],
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------
# Pipeline adapter
# ---------------------------------------------------------------------

def write_pipeline_inputs(
    run_dir: Path,
    rubric_data: Dict[str, Any],
    submission_data: Dict[str, Any],
    previous_answers_data: List[Dict[str, Any]],
) -> Tuple[Path, Path, Path]:
    run_dir.mkdir(parents=True, exist_ok=True)

    rubric_path = run_dir / "_input_rubric.json"
    submission_path = run_dir / "_input_submission.json"
    previous_path = run_dir / "_input_previous.json"

    rubric_path.write_text(json_dumps(rubric_data), encoding="utf-8")
    submission_path.write_text(json_dumps(submission_data), encoding="utf-8")
    previous_path.write_text(
        json_dumps({"previous_answers": previous_answers_data}),
        encoding="utf-8",
    )

    return rubric_path, submission_path, previous_path


def accepted_kwargs(callable_obj: Any, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    try:
        signature = inspect.signature(callable_obj)
    except Exception:
        return kwargs

    params = signature.parameters

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values()):
        return kwargs

    return {
        key: value
        for key, value in kwargs.items()
        if key in params
    }


def instantiate_pipeline_flexibly(kwargs: Dict[str, Any]) -> Any:
    """
    Tries to instantiate FeedbackGradingPipeline with several likely signatures.
    """
    errors: List[str] = []

    constructor_kwargs = accepted_kwargs(FeedbackGradingPipeline, kwargs)

    attempts = [
        lambda: FeedbackGradingPipeline(**constructor_kwargs),
        lambda: FeedbackGradingPipeline(),
        lambda: FeedbackGradingPipeline(
            kwargs["rubric"],
            kwargs["submission"],
            kwargs["previous_answers"],
            kwargs["output_dir"],
        ),
        lambda: FeedbackGradingPipeline(
            kwargs["rubric_data"],
            kwargs["submission_data"],
            kwargs["previous_answers_data"],
            kwargs["output_dir"],
        ),
        lambda: FeedbackGradingPipeline(
            kwargs["rubric_path"],
            kwargs["submission_path"],
            kwargs["previous_path"],
            kwargs["output_dir"],
        ),
    ]

    for attempt in attempts:
        try:
            return attempt()
        except Exception as exc:
            errors.append(str(exc))

    raise RuntimeError(
        "Could not instantiate FeedbackGradingPipeline.\n\n"
        + "\n".join(errors[-5:])
    )


def call_pipeline_method_flexibly(pipeline: Any, kwargs: Dict[str, Any]) -> Any:
    """
    Tries common pipeline method names and argument styles.
    """
    candidate_methods = [
        "run",
        "execute",
        "process",
        "evaluate",
        "run_pipeline",
        "generate",
    ]

    errors: List[str] = []

    for method_name in candidate_methods:
        method = getattr(pipeline, method_name, None)
        if not callable(method):
            continue

        method_kwargs = accepted_kwargs(method, kwargs)

        attempts = [
            lambda: method(**method_kwargs),
            lambda: method(),
            lambda: method(
                kwargs["rubric"],
                kwargs["submission"],
                kwargs["previous_answers"],
            ),
            lambda: method(
                kwargs["rubric"],
                kwargs["submission"],
                kwargs["previous_answers"],
                kwargs["output_dir"],
            ),
            lambda: method(
                kwargs["rubric_path"],
                kwargs["submission_path"],
                kwargs["previous_path"],
                kwargs["output_dir"],
            ),
        ]

        for attempt in attempts:
            try:
                return attempt()
            except TypeError as exc:
                errors.append(f"{method_name}: {exc}")
                continue
            except Exception as exc:
                errors.append(f"{method_name}: {exc}")
                break

    if callable(pipeline):
        try:
            return pipeline(**accepted_kwargs(pipeline, kwargs))
        except Exception as exc:
            errors.append(f"callable pipeline: {exc}")

    raise RuntimeError(
        "Could not execute FeedbackGradingPipeline.\n\n"
        + "\n".join(errors[-8:])
    )


def run_cli_pipeline_fallback(
    rubric_path: Path,
    submission_path: Path,
    previous_path: Path,
    output_dir: Path,
) -> None:
    """
    Fallback: use the existing CLI entrypoint if the in-memory class signature
    does not match the adapter.

    This still reuses the backend pipeline through run_pipeline.py.
    """
    cmd = [
        sys.executable,
        "-m",
        "src.feedback_grading.run_pipeline",
        "--rubric",
        str(rubric_path),
        "--submission",
        str(submission_path),
        "--previous",
        str(previous_path),
        "--out",
        str(output_dir),
    ]

    completed = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )

    if completed.returncode != 0:
        raise RuntimeError(
            "Pipeline CLI fallback failed.\n\n"
            f"STDOUT:\n{completed.stdout}\n\n"
            f"STDERR:\n{completed.stderr}"
        )


def collect_pipeline_outputs(
    pipeline_result: Any,
    output_dir: Path,
) -> Tuple[Dict[str, Any], str]:
    """
    Collect JSON and Markdown outputs from:
    - the direct pipeline return value
    - files written by the pipeline
    """
    result_data: Dict[str, Any] = {}
    report_md = ""

    plain = to_plain_data(pipeline_result)

    if isinstance(plain, tuple) and len(plain) >= 2:
        first, second = plain[0], plain[1]
        if isinstance(first, Mapping):
            result_data = dict(first)
        if isinstance(second, str):
            report_md = second

    elif isinstance(plain, Mapping):
        result_data = dict(plain)

        possible_report = (
            result_data.get("markdown_report")
            or result_data.get("report_markdown")
            or result_data.get("report")
            or result_data.get("markdown")
        )

        if isinstance(possible_report, str):
            report_md = possible_report

    elif isinstance(plain, str):
        try:
            parsed = parse_json_text(plain)
            if isinstance(parsed, Mapping):
                result_data = dict(parsed)
        except Exception:
            report_md = plain

    json_files = sorted(
        [
            path for path in output_dir.glob("*.json")
            if not path.name.startswith("_input_")
        ],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    md_files = sorted(
        list(output_dir.glob("*.md")),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not result_data and json_files:
        result_data = json.loads(json_files[0].read_text(encoding="utf-8"))

    if not report_md and md_files:
        report_md = md_files[0].read_text(encoding="utf-8")

    if not report_md and result_data:
        report_md = "# Feedback and Grading Support Report\n\n"
        report_md += "No Markdown report was returned by the backend pipeline.\n\n"
        report_md += "```json\n"
        report_md += json_dumps(result_data)
        report_md += "\n```"

    return result_data, report_md


def run_pipeline_for_submission(
    rubric_data: Dict[str, Any],
    submission_data: Dict[str, Any],
    previous_answers_data: List[Dict[str, Any]],
    submission_output_dir: Path,
) -> Tuple[Dict[str, Any], str]:
    require_backend()

    rubric_path, submission_path, previous_path = write_pipeline_inputs(
        submission_output_dir,
        rubric_data,
        submission_data,
        previous_answers_data,
    )

    rubric_obj = build_schema_instance(Rubric, rubric_data)
    submission_obj = build_schema_instance(StudentSubmission, submission_data)
    previous_objs = [
        build_schema_instance(PreviousGradedAnswer, item)
        for item in previous_answers_data
    ]

    kwargs = {
        "rubric": rubric_obj,
        "rubric_data": rubric_data,
        "rubric_path": str(rubric_path),
        "student_submission": submission_obj,
        "submission": submission_obj,
        "submission_data": submission_data,
        "submission_path": str(submission_path),
        "previous_answers": previous_objs,
        "previous_graded_answers": previous_objs,
        "previous_answers_data": previous_answers_data,
        "previous_data": previous_answers_data,
        "previous_path": str(previous_path),
        "output_dir": str(submission_output_dir),
        "out_dir": str(submission_output_dir),
        "out": str(submission_output_dir),
    }

    pipeline_result = None
    direct_error: Optional[Exception] = None

    try:
        pipeline = instantiate_pipeline_flexibly(kwargs)
        pipeline_result = call_pipeline_method_flexibly(pipeline, kwargs)
    except Exception as exc:
        direct_error = exc

    if direct_error is not None:
        try:
            run_cli_pipeline_fallback(
                rubric_path=rubric_path,
                submission_path=submission_path,
                previous_path=previous_path,
                output_dir=submission_output_dir,
            )
        except Exception as cli_error:
            raise RuntimeError(
                "Both direct FeedbackGradingPipeline execution and CLI fallback failed.\n\n"
                f"Direct execution error:\n{direct_error}\n\n"
                f"CLI fallback error:\n{cli_error}"
            ) from cli_error

    return collect_pipeline_outputs(pipeline_result, submission_output_dir)


def extract_summary_row(
    student_id: str,
    result_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extracts a consistent summary row from potentially varied backend output keys.
    """
    data = to_plain_data(result_data)
    if not isinstance(data, Mapping):
        data = {}

    score = first_value(
        data,
        [
            ["indicative_score"],
            ["recommended_reference_score"],
            ["grading", "indicative_score"],
            ["grading_result", "indicative_score"],
            ["evaluation", "indicative_score"],
            ["score"],
            ["total_score"],
        ],
    )

    total_possible = first_value(
        data,
        [
            ["total_possible"],
            ["total_possible_score"],
            ["max_score"],
            ["max_points"],
            ["grading", "total_possible"],
            ["grading_result", "total_possible"],
            ["evaluation", "total_possible"],
        ],
    )

    percentage = first_value(
        data,
        [
            ["indicative_percentage"],
            ["percentage"],
            ["grading", "percentage"],
            ["grading_result", "percentage"],
            ["evaluation", "percentage"],
        ],
    )

    avg_similar = first_value(
        data,
        [
            ["average_percentage_of_similar_answers"],
            ["similar_average_percentage"],
            ["average_similar_percentage"],
            ["comparison", "average_percentage_of_similar_answers"],
            ["comparison_result", "average_percentage_of_similar_answers"],
            ["comparison", "average_percentage"],
            ["comparison_result", "average_percentage"],
        ],
    )

    deviation = first_value(
        data,
        [
            ["deviation_from_similar_average"],
            ["deviation"],
            ["comparison", "deviation_from_similar_average"],
            ["comparison_result", "deviation_from_similar_average"],
            ["comparison", "deviation"],
            ["comparison_result", "deviation"],
        ],
    )

    consistency_flag = first_value(
        data,
        [
            ["consistency_flag"],
            ["fairness_consistency_flag"],
            ["comparison", "consistency_flag"],
            ["comparison_result", "consistency_flag"],
            ["comparison", "fairness_consistency_flag"],
            ["comparison_result", "fairness_consistency_flag"],
        ],
        default="not_available",
    )

    score_float = as_float(score)
    total_float = as_float(total_possible)
    percentage_float = as_float(percentage)

    if percentage_float is None and score_float is not None and total_float:
        percentage_float = round((score_float / total_float) * 100, 2)

    return {
        "student_id": student_id,
        "indicative_score": score_float,
        "total_possible": total_float,
        "percentage": percentage_float,
        "consistency_flag": consistency_flag,
        "average_similar_percentage": as_float(avg_similar),
        "deviation_from_similar_average": as_float(deviation),
    }


def save_batch_outputs(
    run_dir: Path,
    rubric_data: Dict[str, Any],
    previous_answers_data: List[Dict[str, Any]],
    submissions_data: List[Dict[str, Any]],
    batch_results: List[Dict[str, Any]],
    summary_rows: List[Dict[str, Any]],
    reports: Dict[str, str],
) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = run_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)

    batch_json = {
        "created_at": datetime.now().isoformat(),
        "note": (
            "Lecturer-support output only. Scores are indicative and not final grades."
        ),
        "rubric": rubric_data,
        "previous_answers_count": len(previous_answers_data),
        "submissions_count": len(submissions_data),
        "summary": summary_rows,
        "results": batch_results,
    }

    (run_dir / "batch_results.json").write_text(
        json_dumps(batch_json),
        encoding="utf-8",
    )

    pd.DataFrame(summary_rows).to_csv(
        run_dir / "summary.csv",
        index=False,
    )

    for student_id, report_md in reports.items():
        report_path = reports_dir / f"{safe_filename(student_id)}.md"
        report_path.write_text(report_md, encoding="utf-8")

    zip_path = run_dir / "all_markdown_reports.zip"
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for report_path in reports_dir.glob("*.md"):
            zf.write(report_path, arcname=report_path.name)


# ---------------------------------------------------------------------
# UI shared elements
# ---------------------------------------------------------------------

def render_header() -> None:
    st.title("🎓 Feedback & Grading Support Interface")

    st.warning(
        "This system is a lecturer-support tool. It does not make final academic "
        "grading decisions. AI-generated rubrics must be reviewed by a lecturer. "
        "Indicative scores are references only. Student copies should be anonymised "
        "before processing.",
        icon="⚠️",
    )

    with st.container(border=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Rubric",
                "Validated" if st.session_state.rubric_validated else "Not validated",
            )

        with col2:
            st.metric(
                "Reference copies",
                len(st.session_state.previous_answers_data),
            )

        with col3:
            st.metric(
                "New submissions",
                len(st.session_state.submissions_data),
            )

    st.divider()


def render_sidebar() -> str:
    st.sidebar.title("Workflow")

    steps = [
        "1. Marking Scheme",
        "2. Reference Copies",
        "3. New Submissions",
        "4. Run Analysis",
        "5. Export",
    ]

    page = st.sidebar.radio("Steps", steps)

    st.sidebar.divider()
    st.sidebar.subheader("Status")

    if st.session_state.rubric_validated:
        st.sidebar.success("Rubric validated")
    elif st.session_state.rubric_data:
        st.sidebar.warning("Rubric draft not validated")
    else:
        st.sidebar.info("No rubric yet")

    st.sidebar.metric("Reference copies", len(st.session_state.previous_answers_data))
    st.sidebar.metric("New submissions", len(st.session_state.submissions_data))
    st.sidebar.metric("Batch results", len(st.session_state.batch_results))

    st.sidebar.divider()
    st.sidebar.caption(
        "Use anonymised copy IDs and student IDs. Do not upload directly identifying data."
    )

    return page


# ---------------------------------------------------------------------
# Page 1: Marking scheme setup
# ---------------------------------------------------------------------

def render_rubric_editor(rubric_data: Dict[str, Any]) -> Dict[str, Any]:
    st.subheader("Review and edit rubric")

    edited = dict(rubric_data)
    criteria = list(edited.get("criteria", []))

    col1, col2 = st.columns([1, 2])

    with col1:
        edited["assignment_id"] = st.text_input(
            "Assignment ID",
            value=str(edited.get("assignment_id", "")),
            key="rubric_assignment_id",
        )

    with col2:
        st.metric(
            "Total possible points",
            f"{rubric_total_points(edited):.2f}",
        )

    edited["question"] = st.text_area(
        "Question / assessment task",
        value=str(edited.get("question", "")),
        height=120,
        key="rubric_question",
    )

    st.markdown("### Criteria")

    if st.button("➕ Add criterion"):
        criteria.append(
            {
                "criterion_id": f"C{len(criteria) + 1}",
                "name": "New criterion",
                "description": "",
                "max_points": 0.0,
                "expected_elements": [],
                "common_errors": [],
                "feedback_guidance": "",
            }
        )

    updated_criteria = []

    for index, criterion in enumerate(criteria):
        criterion = normalize_criterion(criterion, index)

        with st.expander(
            f"{criterion.get('criterion_id')} — {criterion.get('name')}",
            expanded=index == 0,
        ):
            c1, c2, c3 = st.columns([1, 2, 1])

            with c1:
                criterion["criterion_id"] = st.text_input(
                    "Criterion ID",
                    value=str(criterion.get("criterion_id", "")),
                    key=f"criterion_id_{index}",
                )

            with c2:
                criterion["name"] = st.text_input(
                    "Criterion name",
                    value=str(criterion.get("name", "")),
                    key=f"criterion_name_{index}",
                )

            with c3:
                criterion["max_points"] = st.number_input(
                    "Max points",
                    min_value=0.0,
                    value=float(criterion.get("max_points", 0.0)),
                    step=0.5,
                    key=f"criterion_max_points_{index}",
                )

            criterion["description"] = st.text_area(
                "Description",
                value=str(criterion.get("description", "")),
                height=80,
                key=f"criterion_description_{index}",
            )

            criterion["expected_elements"] = text_to_list(
                st.text_area(
                    "Expected elements — one per line",
                    value=list_to_text(criterion.get("expected_elements", [])),
                    height=130,
                    key=f"criterion_expected_{index}",
                )
            )

            criterion["common_errors"] = text_to_list(
                st.text_area(
                    "Common errors — one per line",
                    value=list_to_text(criterion.get("common_errors", [])),
                    height=100,
                    key=f"criterion_errors_{index}",
                )
            )

            criterion["feedback_guidance"] = st.text_area(
                "Feedback guidance",
                value=str(criterion.get("feedback_guidance", "")),
                height=100,
                key=f"criterion_feedback_{index}",
            )

            remove = st.checkbox(
                "Remove this criterion",
                key=f"remove_criterion_{index}",
            )

            if not remove:
                updated_criteria.append(criterion)

    edited["criteria"] = updated_criteria

    return edited


def page_marking_scheme() -> None:
    require_backend()

    st.header("1. Marking Scheme Setup")

    st.info(
        "AI extraction is only a draft. A lecturer must review and validate the rubric before analysis.",
        icon="ℹ️",
    )

    input_mode = st.radio(
        "Choose marking scheme input mode",
        [
            "Paste raw marking scheme text",
            "Upload .txt marking scheme",
            "Upload .json rubric directly",
            "Experimental OCR / PDF / image upload",
        ],
    )

    if input_mode == "Paste raw marking scheme text":
        raw_text = st.text_area(
            "Paste raw marking scheme text",
            height=260,
            placeholder="Paste the official marking scheme or lecturer marking notes here...",
        )

        if st.button("Generate draft rubric with Mistral"):
            try:
                with st.spinner("Generating structured rubric draft..."):
                    st.session_state.rubric_data = parse_rubric_with_ai(raw_text)
                    st.session_state.rubric_validated = False
                st.success("Draft rubric generated. Please review and validate it.")
            except Exception as exc:
                st.error("Could not generate rubric from raw text.")
                with st.expander("Technical details"):
                    st.code(str(exc))

    elif input_mode == "Upload .txt marking scheme":
        uploaded = st.file_uploader(
            "Upload a .txt marking scheme",
            type=["txt"],
            accept_multiple_files=False,
        )

        if uploaded and st.button("Generate draft rubric from .txt"):
            try:
                raw_text = load_uploaded_text(uploaded)
                with st.spinner("Generating structured rubric draft..."):
                    st.session_state.rubric_data = parse_rubric_with_ai(raw_text)
                    st.session_state.rubric_validated = False
                st.success("Draft rubric generated. Please review and validate it.")
            except Exception as exc:
                st.error("Could not generate rubric from uploaded text.")
                with st.expander("Technical details"):
                    st.code(str(exc))

    elif input_mode == "Upload .json rubric directly":
        uploaded = st.file_uploader(
            "Upload rubric JSON",
            type=["json"],
            accept_multiple_files=False,
        )

        if uploaded and st.button("Load rubric JSON"):
            try:
                payload = load_uploaded_json(uploaded)
                st.session_state.rubric_data = normalize_rubric_data(payload)
                st.session_state.rubric_validated = False
                st.success("Rubric JSON loaded. Please review and validate it.")
            except Exception as exc:
                st.error("Could not load rubric JSON.")
                with st.expander("Technical details"):
                    st.code(str(exc))

    else:
        st.warning(
            "OCR/PDF/image ingestion is reserved for a future version. "
            "For now, use pasted text, .txt upload, or structured .json upload.",
            icon="⚠️",
        )
        st.caption(
            "Recommended future implementation: PDF/image upload → OCR model → raw marking scheme text → RubricAIParser → lecturer validation."
        )

    if st.session_state.rubric_data:
        st.divider()

        edited = render_rubric_editor(st.session_state.rubric_data)
        st.session_state.rubric_data = edited

        c1, c2, c3 = st.columns([1, 1, 2])

        with c1:
            if st.button("✅ Validate rubric for analysis"):
                try:
                    validate_rubric_with_backend(st.session_state.rubric_data)
                    st.session_state.rubric_validated = True
                    st.success("Rubric validated successfully.")
                except Exception as exc:
                    st.session_state.rubric_validated = False
                    st.error("Rubric validation failed.")
                    with st.expander("Technical details"):
                        st.code(str(exc))

        with c2:
            if st.button("Reset rubric"):
                st.session_state.rubric_data = None
                st.session_state.rubric_validated = False
                st.warning("Rubric reset.")

        with c3:
            st.download_button(
                "Download current rubric JSON",
                data=json_dumps(st.session_state.rubric_data),
                file_name="validated_rubric_draft.json",
                mime="application/json",
            )

        with st.expander("Preview current rubric JSON"):
            st.code(json_dumps(st.session_state.rubric_data), language="json")


# ---------------------------------------------------------------------
# Page 2: Reference corrected copies
# ---------------------------------------------------------------------

def page_reference_copies() -> None:
    st.header("2. Reference Corrected Copies")

    st.info(
        "Use previous anonymised corrected copies as a fairness and consistency reference. "
        "They are not an automatic grading decision.",
        icon="ℹ️",
    )

    tab_manual, tab_upload = st.tabs(["Manual entry", "Upload JSON"])

    with tab_manual:
        with st.form("previous_copy_form"):
            copy_id = st.text_input("Copy ID", placeholder="copy_A001")
            answer = st.text_area("Answer", height=200)
            c1, c2 = st.columns(2)
            with c1:
                score = st.number_input("Score", min_value=0.0, step=0.5)
            with c2:
                max_score = st.number_input("Max score", min_value=0.1, value=6.0, step=0.5)
            grader_id = st.text_input("Grader ID", placeholder="grader_1")
            lecturer_comment = st.text_area("Lecturer comment", height=100)

            submitted = st.form_submit_button("Add previous corrected copy")

            if submitted:
                try:
                    item = validate_previous_answer(
                        {
                            "copy_id": copy_id,
                            "answer": answer,
                            "score": score,
                            "max_score": max_score,
                            "grader_id": grader_id,
                            "lecturer_comment": lecturer_comment,
                        },
                        index=len(st.session_state.previous_answers_data),
                    )
                    st.session_state.previous_answers_data.append(item)
                    st.success(f"Added {item['copy_id']}.")
                except Exception as exc:
                    st.error(str(exc))

    with tab_upload:
        st.markdown("Expected JSON format:")
        st.code(
            json_dumps(
                {
                    "previous_answers": [
                        {
                            "copy_id": "copy_A001",
                            "answer": "student answer text",
                            "score": 5.5,
                            "max_score": 6,
                            "grader_id": "grader_1",
                            "lecturer_comment": "comment",
                        }
                    ]
                }
            ),
            language="json",
        )

        uploaded = st.file_uploader(
            "Upload previous corrected copies JSON",
            type=["json"],
            accept_multiple_files=False,
            key="previous_upload",
        )

        replace_existing = st.checkbox("Replace existing reference copies", value=False)

        if uploaded and st.button("Import previous corrected copies"):
            try:
                payload = load_uploaded_json(uploaded)
                imported = validate_previous_payload(payload)

                if replace_existing:
                    st.session_state.previous_answers_data = imported
                else:
                    st.session_state.previous_answers_data.extend(imported)

                st.success(f"Imported {len(imported)} previous corrected copies.")
            except Exception as exc:
                st.error("Could not import previous corrected copies.")
                with st.expander("Technical details"):
                    st.code(str(exc))

    st.divider()
    st.subheader("Current previous corrected copies")

    if st.session_state.previous_answers_data:
        st.dataframe(previous_answers_dataframe(), use_container_width=True)

        c1, c2 = st.columns(2)

        with c1:
            st.download_button(
                "Download previous copies JSON",
                data=json_dumps(
                    {"previous_answers": st.session_state.previous_answers_data}
                ),
                file_name="previous_answers.json",
                mime="application/json",
            )

        with c2:
            if st.button("Clear all previous copies"):
                st.session_state.previous_answers_data = []
                st.warning("Previous corrected copies cleared.")
    else:
        st.warning(
            "No previous corrected copies added yet. You can still run analysis, "
            "but consistency comparison may be unavailable.",
            icon="⚠️",
        )


# ---------------------------------------------------------------------
# Page 3: New submissions
# ---------------------------------------------------------------------

def page_new_submissions() -> None:
    st.header("3. New Student Copies")

    st.info(
        "Add anonymised submissions only. Use student IDs such as student_001, not names or emails.",
        icon="ℹ️",
    )

    tab_manual, tab_upload = st.tabs(["Manual entry", "Upload JSON"])

    with tab_manual:
        with st.form("submission_form"):
            student_id = st.text_input("Student ID", placeholder="student_001")
            answer = st.text_area("Student answer", height=240)

            metadata_text = st.text_area(
                "Optional metadata as JSON",
                value='{"course": "Engineering", "year": "first_year"}',
                height=120,
            )

            submitted = st.form_submit_button("Add submission")

            if submitted:
                try:
                    metadata = {}
                    if metadata_text.strip():
                        metadata = parse_json_text(metadata_text)

                    item = validate_submission(
                        {
                            "student_id": student_id,
                            "answer": answer,
                            "metadata": metadata,
                        },
                        index=len(st.session_state.submissions_data),
                    )

                    st.session_state.submissions_data.append(item)
                    st.success(f"Added {item['student_id']}.")
                except Exception as exc:
                    st.error(str(exc))

    with tab_upload:
        st.markdown("Expected JSON format:")
        st.code(
            json_dumps(
                {
                    "submissions": [
                        {
                            "student_id": "student_001",
                            "answer": "student answer text",
                            "metadata": {
                                "course": "Engineering",
                                "year": "first_year",
                            },
                        }
                    ]
                }
            ),
            language="json",
        )

        uploaded = st.file_uploader(
            "Upload submissions JSON",
            type=["json"],
            accept_multiple_files=False,
            key="submissions_upload",
        )

        replace_existing = st.checkbox("Replace existing submissions", value=False)

        if uploaded and st.button("Import submissions"):
            try:
                payload = load_uploaded_json(uploaded)
                imported = validate_submissions_payload(payload)

                if replace_existing:
                    st.session_state.submissions_data = imported
                else:
                    st.session_state.submissions_data.extend(imported)

                st.success(f"Imported {len(imported)} submissions.")
            except Exception as exc:
                st.error("Could not import submissions.")
                with st.expander("Technical details"):
                    st.code(str(exc))

    st.divider()
    st.subheader("Current submissions")

    if st.session_state.submissions_data:
        st.dataframe(submissions_dataframe(), use_container_width=True)

        c1, c2 = st.columns(2)

        with c1:
            st.download_button(
                "Download submissions JSON",
                data=json_dumps({"submissions": st.session_state.submissions_data}),
                file_name="submissions.json",
                mime="application/json",
            )

        with c2:
            if st.button("Clear all submissions"):
                st.session_state.submissions_data = []
                st.warning("Submissions cleared.")
    else:
        st.warning("No new submissions added yet.", icon="⚠️")


# ---------------------------------------------------------------------
# Page 4: Run batch evaluation
# ---------------------------------------------------------------------

def page_run_analysis() -> None:
    st.header("4. Run Batch Evaluation")

    st.markdown(
        """
This step runs the existing backend pipeline for every new submission.

The generated results are:

- indicative score
- total possible score
- indicative percentage
- criterion-by-criterion evaluation
- comparison with similar previous anonymised copies
- fairness / consistency reference
- Markdown report for lecturer review
        """
    )

    if not st.session_state.rubric_data:
        st.error("No rubric has been created or uploaded yet.")
        return

    if not st.session_state.rubric_validated:
        st.error("The rubric must be reviewed and validated before running analysis.")
        return

    if not st.session_state.submissions_data:
        st.error("No new submissions have been provided.")
        return

    if not st.session_state.previous_answers_data:
        st.warning(
            "No previous corrected copies are available. The grading analysis can run, "
            "but consistency comparison may be limited or unavailable.",
            icon="⚠️",
        )

    st.subheader("Readiness check")

    with st.container(border=True):
        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric("Rubric status", "Validated")
            st.success("Lecturer validation completed.", icon="✅")

        with c2:
            st.metric(
                "Previous corrected copies",
                len(st.session_state.previous_answers_data),
            )
            if st.session_state.previous_answers_data:
                st.info("Consistency reference available.", icon="ℹ️")
            else:
                st.warning("No consistency reference available.", icon="⚠️")

        with c3:
            st.metric(
                "New submissions",
                len(st.session_state.submissions_data),
            )
            st.info("Batch mode enabled.", icon="📦")

    st.divider()

    if st.button("🚀 Run Feedback and Grading Analysis", type="primary"):
        run_dir = OUTPUT_ROOT / now_run_id()
        run_dir.mkdir(parents=True, exist_ok=True)

        summary_rows: List[Dict[str, Any]] = []
        batch_results: List[Dict[str, Any]] = []
        reports: Dict[str, str] = {}
        errors: List[Dict[str, str]] = []

        progress = st.progress(0)
        status = st.empty()

        total = len(st.session_state.submissions_data)

        for index, submission in enumerate(st.session_state.submissions_data):
            student_id = str(submission.get("student_id", f"student_{index + 1}"))
            status.write(f"Processing {student_id} ({index + 1}/{total})...")

            submission_dir = run_dir / safe_filename(student_id)

            try:
                result_data, report_md = run_pipeline_for_submission(
                    rubric_data=st.session_state.rubric_data,
                    submission_data=submission,
                    previous_answers_data=st.session_state.previous_answers_data,
                    submission_output_dir=submission_dir,
                )

                summary = extract_summary_row(student_id, result_data)
                summary_rows.append(summary)

                batch_results.append(
                    {
                        "student_id": student_id,
                        "result": result_data,
                        "report_path": str(submission_dir),
                    }
                )

                reports[student_id] = report_md

            except Exception as exc:
                errors.append(
                    {
                        "student_id": student_id,
                        "error": str(exc),
                    }
                )

            progress.progress((index + 1) / total)

        if errors:
            st.warning(
                f"Analysis completed with {len(errors)} error(s). "
                "Successful submissions are still available below.",
                icon="⚠️",
            )
            with st.expander("Processing errors"):
                st.dataframe(pd.DataFrame(errors), use_container_width=True)

        if summary_rows:
            save_batch_outputs(
                run_dir=run_dir,
                rubric_data=st.session_state.rubric_data,
                previous_answers_data=st.session_state.previous_answers_data,
                submissions_data=st.session_state.submissions_data,
                batch_results=batch_results,
                summary_rows=summary_rows,
                reports=reports,
            )

            st.session_state.batch_results = batch_results
            st.session_state.summary_rows = summary_rows
            st.session_state.reports = reports
            st.session_state.last_run_dir = str(run_dir)

            st.success("Batch analysis completed.", icon="✅")
        else:
            st.error("No submissions were processed successfully.")

    st.divider()

    if st.session_state.summary_rows:
        st.subheader("Summary table")

        summary_df = pd.DataFrame(st.session_state.summary_rows)
        st.dataframe(summary_df, use_container_width=True)

        st.subheader("Detailed report viewer")

        student_ids = list(st.session_state.reports.keys())
        selected_student = st.selectbox("Select student", student_ids)

        if selected_student:
            st.markdown(st.session_state.reports[selected_student])


# ---------------------------------------------------------------------
# Page 5: Export
# ---------------------------------------------------------------------

def page_export() -> None:
    st.header("5. Export Results")

    if not st.session_state.batch_results:
        st.warning("No batch results are available yet. Run the analysis first.", icon="⚠️")
        return

    run_dir = Path(st.session_state.last_run_dir) if st.session_state.last_run_dir else None

    if run_dir:
        st.info(f"Latest outputs saved locally to: `{run_dir}`", icon="ℹ️")

    summary_df = pd.DataFrame(st.session_state.summary_rows)

    batch_payload = {
        "created_at": datetime.now().isoformat(),
        "note": "Lecturer-support output only. Indicative scores are not final grades.",
        "summary": st.session_state.summary_rows,
        "results": st.session_state.batch_results,
    }

    col1, col2 = st.columns(2)

    with col1:
        st.download_button(
            "Download batch results JSON",
            data=json_dumps(batch_payload),
            file_name="streamlit_batch_results.json",
            mime="application/json",
        )

    with col2:
        csv_data = summary_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download summary CSV",
            data=csv_data,
            file_name="streamlit_summary.csv",
            mime="text/csv",
        )

    st.divider()

    st.subheader("Individual Markdown report")

    student_ids = list(st.session_state.reports.keys())
    selected_student = st.selectbox("Select report to export", student_ids)

    if selected_student:
        report_md = st.session_state.reports[selected_student]
        st.download_button(
            "Download selected Markdown report",
            data=report_md,
            file_name=f"{safe_filename(selected_student)}_report.md",
            mime="text/markdown",
        )

    st.divider()

    st.subheader("All Markdown reports")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for student_id, report_md in st.session_state.reports.items():
            zf.writestr(f"{safe_filename(student_id)}_report.md", report_md)

    st.download_button(
        "Download all Markdown reports as ZIP",
        data=zip_buffer.getvalue(),
        file_name="all_markdown_reports.zip",
        mime="application/zip",
    )

    if run_dir and run_dir.exists():
        with st.expander("Files written to disk"):
            for path in sorted(run_dir.rglob("*")):
                if path.is_file():
                    st.write(f"- `{path.relative_to(run_dir)}`")


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:
    render_header()
    page = render_sidebar()

    if page == "1. Marking Scheme":
        page_marking_scheme()
    elif page == "2. Reference Copies":
        page_reference_copies()
    elif page == "3. New Submissions":
        page_new_submissions()
    elif page == "4. Run Analysis":
        page_run_analysis()
    elif page == "5. Export":
        page_export()


if __name__ == "__main__":
    main()