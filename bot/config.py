"""Configuration loaded from environment variables."""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""

    # Matrix
    MATRIX_HOMESERVER = os.getenv("MATRIX_HOMESERVER", "http://dendrite:8008")
    MATRIX_USER_ID = os.getenv("MATRIX_USER_ID")
    MATRIX_PASSWORD = os.getenv("MATRIX_PASSWORD")
    MATRIX_INBOX_ROOM = os.getenv("MATRIX_INBOX_ROOM")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")

    # LLM - Classification (cheap, fast)
    CLASSIFY_PROVIDER = os.getenv("CLASSIFY_PROVIDER", "openai")
    CLASSIFY_API_URL = os.getenv("CLASSIFY_API_URL")
    CLASSIFY_API_KEY = os.getenv("CLASSIFY_API_KEY")
    CLASSIFY_MODEL = os.getenv("CLASSIFY_MODEL", "glm-4")

    # LLM - Summary (quality matters)
    SUMMARY_PROVIDER = os.getenv("SUMMARY_PROVIDER", "openai")
    SUMMARY_API_URL = os.getenv("SUMMARY_API_URL")
    SUMMARY_API_KEY = os.getenv("SUMMARY_API_KEY")
    SUMMARY_MODEL = os.getenv("SUMMARY_MODEL", "anthropic/claude-sonnet-4")

    # Settings
    CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.6"))
    DIGEST_TARGET_USER = os.getenv("DIGEST_TARGET_USER")

    # Per-category thresholds (optional override)
    CONFIDENCE_THRESHOLDS = {
        "people": float(os.getenv("CONFIDENCE_THRESHOLD_PEOPLE", "0.6")),
        "projects": float(os.getenv("CONFIDENCE_THRESHOLD_PROJECTS", "0.6")),
        "ideas": float(os.getenv("CONFIDENCE_THRESHOLD_IDEAS", "0.5")),
        "admin": float(os.getenv("CONFIDENCE_THRESHOLD_ADMIN", "0.6")),
    }

    # Cached LLM clients
    _classify_client = None
    _summary_client = None

    @classmethod
    def get_threshold(cls, category: str) -> float:
        """Get confidence threshold for a category."""
        return cls.CONFIDENCE_THRESHOLDS.get(category, cls.CONFIDENCE_THRESHOLD)

    @classmethod
    def get_classify_client(cls):
        """Get or create the classification LLM client."""
        if cls._classify_client is None:
            from llm.factory import create_client

            cls._classify_client = create_client(
                provider=cls.CLASSIFY_PROVIDER,
                api_url=cls.CLASSIFY_API_URL,
                api_key=cls.CLASSIFY_API_KEY,
                model=cls.CLASSIFY_MODEL,
            )
        return cls._classify_client

    @classmethod
    def get_summary_client(cls):
        """Get or create the summary LLM client."""
        if cls._summary_client is None:
            from llm.factory import create_client

            cls._summary_client = create_client(
                provider=cls.SUMMARY_PROVIDER,
                api_url=cls.SUMMARY_API_URL,
                api_key=cls.SUMMARY_API_KEY,
                model=cls.SUMMARY_MODEL,
            )
        return cls._summary_client

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of missing vars."""
        required = [
            ("MATRIX_USER_ID", cls.MATRIX_USER_ID),
            ("MATRIX_PASSWORD", cls.MATRIX_PASSWORD),
            ("MATRIX_INBOX_ROOM", cls.MATRIX_INBOX_ROOM),
            ("DATABASE_URL", cls.DATABASE_URL),
            ("CLASSIFY_API_URL", cls.CLASSIFY_API_URL),
            ("CLASSIFY_API_KEY", cls.CLASSIFY_API_KEY),
            ("SUMMARY_API_URL", cls.SUMMARY_API_URL),
            ("SUMMARY_API_KEY", cls.SUMMARY_API_KEY),
            ("DIGEST_TARGET_USER", cls.DIGEST_TARGET_USER),
        ]
        return [name for name, value in required if not value]
