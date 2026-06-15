import json
import re
from typing import Any, Dict

from .mistral_client import get_mistral_client, get_text_model
from .schemas import Rubric, SchemaValidationError


SYSTEM_PROMPT = """
You are an academic rubric extraction assistant.

Convert the raw marking scheme into STRICT valid JSON.

Return ONLY JSON.
No markdown.
No explanation.
No text before or after the JSON.

The JSON must follow this exact structure:

{
  "assignment_id": "string",
  "question": "string",
  "criteria": [
    {
      "id": "C1",
      "title": "string",
      "max_points": 2,
      "expected_elements": ["string"],
      "common_errors": ["string"],
      "feedback_guidance": "string",
      "evidence_required": true
    }
  ]
}

Rules:
- Do not invent unsupported criteria.
- Use the official marking scheme as the authority.
- max_points must be a number.
- expected_elements must describe what the student answer must contain.
- common_errors should include likely mistakes if they are mentioned or strongly implied.
- If the question is missing, infer a short question title from the marking scheme.
"""


def extract_message_content(response: Any) -> str:
    """
    Robustly extract assistant content from Mistral SDK responses.
    """
    try:
        content = response.choices[0].message.content
    except Exception:
        try:
            content = response["choices"][0]["message"]["content"]
        except Exception as exc:
            raise RuntimeError(f"Could not extract content from Mistral response: {response}") from exc

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        chunks = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    chunks.append(item.get("text", ""))
                elif "text" in item:
                    chunks.append(item["text"])
            else:
                text = getattr(item, "text", None)
                if text:
                    chunks.append(text)
        return "\n".join(chunks)

    return str(content)


def extract_json(text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from a model response.
    """
    text = text.strip()

    if text.startswith("```"):
        text = re.sub(r"^```json", "", text.strip(), flags=re.IGNORECASE)
        text = re.sub(r"^```", "", text.strip())
        text = re.sub(r"```$", "", text.strip())

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in model response:\n{text}")

    return json.loads(match.group(0))


class RubricAIParser:
    """
    Uses Mistral to convert a raw marking scheme into a structured rubric JSON.
    The generated JSON is then validated with the local Rubric schema.
    """

    def __init__(self) -> None:
        self.client = get_mistral_client()
        self.model = get_text_model()

    def _call_mistral(self, raw_marking_scheme: str, assignment_id: str) -> str:
        user_prompt = f"""
Assignment ID to use if none is present: {assignment_id}

Raw marking scheme:
---
{raw_marking_scheme}
---
"""

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        # First try JSON mode. If the installed SDK/model does not accept it,
        # fall back to a normal chat completion.
        try:
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.0,
                response_format={"type": "json_object"},
            )
        except TypeError:
            response = self.client.chat.complete(
                model=self.model,
                messages=messages,
                temperature=0.0,
            )

        return extract_message_content(response)

    def parse_marking_scheme(
        self,
        raw_marking_scheme: str,
        assignment_id: str = "assignment_unknown",
    ) -> Dict[str, Any]:
        content = self._call_mistral(raw_marking_scheme, assignment_id)
        rubric_data = extract_json(content)

        if not rubric_data.get("assignment_id"):
            rubric_data["assignment_id"] = assignment_id

        try:
            Rubric.from_dict(rubric_data)
        except SchemaValidationError as error:
            raise ValueError(
                f"AI-generated rubric failed local schema validation: {error}\n\n"
                f"Generated rubric was:\n{json.dumps(rubric_data, indent=2)}"
            )

        return rubric_data
