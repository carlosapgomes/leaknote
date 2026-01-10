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
    GLM_API_URL = os.getenv("GLM_API_URL")
    GLM_API_KEY = os.getenv("GLM_API_KEY")
    GLM_MODEL = os.getenv("GLM_MODEL", "glm-4")

    # LLM - Summaries (quality matters)
    CLAUDE_API_URL = os.getenv("CLAUDE_API_URL", "https://api.anthropic.com/v1/messages")
    CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
    CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

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
            ("GLM_API_URL", cls.GLM_API_URL),
            ("GLM_API_KEY", cls.GLM_API_KEY),
            ("CLAUDE_API_KEY", cls.CLAUDE_API_KEY),
            ("DIGEST_TARGET_USER", cls.DIGEST_TARGET_USER),
        ]
        return [name for name, value in required if not value]
