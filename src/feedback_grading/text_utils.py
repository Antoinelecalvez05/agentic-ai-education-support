import re
from difflib import SequenceMatcher
from typing import List, Set


STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with",
    "is", "are", "was", "were", "this", "that", "it", "as", "by",
    "on", "from", "at", "be", "can", "will", "should", "would"
}


def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9\s=\/\+\-\*\.]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def tokenize(text: str) -> List[str]:
    normalized = normalize_text(text)
    return [t for t in normalized.split() if t and t not in STOPWORDS]


def token_set(text: str) -> Set[str]:
    return set(tokenize(text))


def phrase_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_text(a), normalize_text(b)).ratio()


def evidence_match(answer: str, expected_element: str) -> float:
    """
    Returns a soft evidence score between 0 and 1.

    It checks:
    - exact phrase presence
    - token overlap
    - fuzzy text similarity

    This is not meant to be a final academic judgement.
    It provides structured evidence for lecturer review.
    """
    answer_norm = normalize_text(answer)
    element_norm = normalize_text(expected_element)

    if not element_norm:
        return 0.0

    if element_norm in answer_norm:
        return 1.0

    answer_tokens = token_set(answer_norm)
    element_tokens = token_set(element_norm)

    if not element_tokens:
        return 0.0

    overlap = len(answer_tokens.intersection(element_tokens)) / len(element_tokens)
    fuzzy = phrase_similarity(answer_norm, element_norm)

    return max(overlap, fuzzy * 0.7)
