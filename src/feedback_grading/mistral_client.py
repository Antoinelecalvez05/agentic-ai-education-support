import os
from dotenv import load_dotenv

load_dotenv()


try:
    from mistralai import Mistral
except ImportError:
    from mistralai.client import Mistral


def get_mistral_client():
    """
    Creates a Mistral client using the API key stored in .env.

    The .env file must contain:
    MISTRAL_API_KEY=your_api_key_here
    """

    api_key = os.getenv("MISTRAL_API_KEY")

    if not api_key:
        raise RuntimeError(
            "MISTRAL_API_KEY is missing. Create a .env file at the project root."
        )

    return Mistral(api_key=api_key)


def get_text_model() -> str:
    """
    Text model used for rubric parsing and feedback generation.
    """

    return os.getenv("MISTRAL_TEXT_MODEL", "mistral-medium-latest")


def get_ocr_model() -> str:
    """
    OCR model used for extracting text from marking scheme documents.
    """

    return os.getenv("MISTRAL_OCR_MODEL", "mistral-ocr-latest")
