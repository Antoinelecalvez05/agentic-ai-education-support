import argparse
import json
from pathlib import Path

from .rubric_ai_parser import RubricAIParser


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse a raw marking scheme into structured rubric JSON using Mistral."
    )

    parser.add_argument("--input", required=True, help="Path to raw marking scheme text file")
    parser.add_argument("--output", required=True, help="Path where rubric JSON should be saved")
    parser.add_argument("--assignment-id", default="assignment_unknown")

    args = parser.parse_args()

    input_path = Path(args.input)
    output_path = Path(args.output)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    raw_text = input_path.read_text(encoding="utf-8")

    parser_ai = RubricAIParser()
    rubric = parser_ai.parse_marking_scheme(
        raw_marking_scheme=raw_text,
        assignment_id=args.assignment_id,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8") as file:
        json.dump(rubric, file, indent=2, ensure_ascii=False)

    print("Rubric generated successfully.")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
