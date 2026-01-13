"""Memory layer configuration."""

import os
from dotenv import load_dotenv

load_dotenv()


class MemoryConfig:
    """Configuration for Mem0 and LangGraph."""

    # Qdrant
    QDRANT_URL = os.getenv("QDRANT_URL", "http://localhost:6333")
    MEM0_COLLECTION = os.getenv("MEM0_COLLECTION", "leaknote_memories")

    # OpenAI API key for embeddings (text-embedding-3-small)
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

    # Memory LLM (for LangGraph orchestration)
    MEMORY_PROVIDER = os.getenv("MEMORY_PROVIDER", "openai")
    MEMORY_API_URL = os.getenv("MEMORY_API_URL")
    MEMORY_API_KEY = os.getenv("MEMORY_API_KEY")
    MEMORY_MODEL = os.getenv("MEMORY_MODEL", "gpt-4o")

    # Settings
    MEMORY_RETRIEVAL_LIMIT = int(os.getenv("MEMORY_RETRIEVAL_LIMIT", "5"))
    MEMORY_CONFIDENCE_THRESHOLD = float(os.getenv("MEMORY_CONFIDENCE_THRESHOLD", "0.7"))

    # User ID for Mem0 (single-user system)
    MEM0_USER_ID = "leaknote_user"

    # Cached client
    _llm_client = None

    @classmethod
    def get_llm_client(cls):
        """Get or create the LLM client for memory operations."""
        if cls._llm_client is None:
            from llm.factory import create_client
            cls._llm_client = create_client(
                provider=cls.MEMORY_PROVIDER,
                api_url=cls.MEMORY_API_URL,
                api_key=cls.MEMORY_API_KEY,
                model=cls.MEMORY_MODEL,
            )
        return cls._llm_client

    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration."""
        required = [
            ("QDRANT_URL", cls.QDRANT_URL),
            ("OPENAI_API_KEY", cls.OPENAI_API_KEY),  # Required for embeddings
            ("MEMORY_API_URL", cls.MEMORY_API_URL),
            ("MEMORY_API_KEY", cls.MEMORY_API_KEY),
        ]
        return [name for name, value in required if not value]
