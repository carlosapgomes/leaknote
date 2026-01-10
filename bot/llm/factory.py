"""Factory for creating LLM clients."""

import os
from typing import Literal

from .base import LLMClient
from .openai_compatible import OpenAICompatibleClient


# Supported client types
ClientType = Literal["openai_compatible"]


def create_llm_client(
    client_type: ClientType = "openai_compatible",
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout: float = 60.0,
) -> LLMClient:
    """
    Create an LLM client instance.

    Args:
        client_type: Type of client to create
        api_key: API key (uses env var if not provided)
        base_url: Base URL (uses env var if not provided)
        timeout: Request timeout in seconds

    Returns:
        Configured LLM client instance

    Raises:
        LLMConfigurationError: If configuration is missing
    """
    if client_type == "openai_compatible":
        return OpenAICompatibleClient(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            timeout=timeout,
        )
    else:
        raise ValueError(f"Unknown client type: {client_type}")


def create_router_client() -> LLMClient:
    """Create LLM client for routing/classification."""
    return OpenAICompatibleClient(
        api_key=os.getenv("ROUTER_LLM_API_KEY"),
        base_url=os.getenv("ROUTER_LLM_BASE_URL"),
        timeout=float(os.getenv("ROUTER_LLM_TIMEOUT", "30.0")),
    )


def create_summarizer_client() -> LLMClient:
    """Create LLM client for summarization."""
    return OpenAICompatibleClient(
        api_key=os.getenv("SUMMARIZER_LLM_API_KEY"),
        base_url=os.getenv("SUMMARIZER_LLM_BASE_URL"),
        timeout=float(os.getenv("SUMMARIZER_LLM_TIMEOUT", "60.0")),
    )
