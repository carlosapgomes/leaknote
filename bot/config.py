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

    # ===================
    # LLM Configuration
    # ===================

    # Router/Classifier LLM (cheap, fast)
    ROUTER_LLM_MODEL = os.getenv("ROUTER_LLM_MODEL", "glm-4")
    ROUTER_LLM_TEMPERATURE = float(os.getenv("ROUTER_LLM_TEMPERATURE", "0.1"))
    ROUTER_LLM_MAX_TOKENS = int(os.getenv("ROUTER_LLM_MAX_TOKENS", "1024"))
    ROUTER_LLM_API_KEY = os.getenv("ROUTER_LLM_API_KEY")
    ROUTER_LLM_BASE_URL = os.getenv("ROUTER_LLM_BASE_URL")
    ROUTER_LLM_TIMEOUT = float(os.getenv("ROUTER_LLM_TIMEOUT", "30.0"))

    # Summarizer LLM (quality matters)
    SUMMARIZER_LLM_MODEL = os.getenv("SUMMARIZER_LLM_MODEL", "claude-sonnet-4-20250514")
    SUMMARIZER_LLM_TEMPERATURE = float(os.getenv("SUMMARIZER_LLM_TEMPERATURE", "0.2"))
    SUMMARIZER_LLM_MAX_TOKENS = int(os.getenv("SUMMARIZER_LLM_MAX_TOKENS", "800"))
    SUMMARIZER_LLM_API_KEY = os.getenv("SUMMARIZER_LLM_API_KEY")
    SUMMARIZER_LLM_BASE_URL = os.getenv("SUMMARIZER_LLM_BASE_URL")
    SUMMARIZER_LLM_TIMEOUT = float(os.getenv("SUMMARIZER_LLM_TIMEOUT", "60.0"))

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

    @classmethod
    def get_threshold(cls, category: str) -> float:
        """Get confidence threshold for a category."""
        return cls.CONFIDENCE_THRESHOLDS.get(category, cls.CONFIDENCE_THRESHOLD)

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration. Returns list of missing vars."""
        required = [
            ("MATRIX_USER_ID", cls.MATRIX_USER_ID),
            ("MATRIX_PASSWORD", cls.MATRIX_PASSWORD),
            ("MATRIX_INBOX_ROOM", cls.MATRIX_INBOX_ROOM),
            ("DATABASE_URL", cls.DATABASE_URL),
            ("ROUTER_LLM_API_KEY", cls.ROUTER_LLM_API_KEY),
            ("ROUTER_LLM_BASE_URL", cls.ROUTER_LLM_BASE_URL),
            ("SUMMARIZER_LLM_API_KEY", cls.SUMMARIZER_LLM_API_KEY),
            ("SUMMARIZER_LLM_BASE_URL", cls.SUMMARIZER_LLM_BASE_URL),
            ("DIGEST_TARGET_USER", cls.DIGEST_TARGET_USER),
        ]
        return [name for name, value in required if not value]
