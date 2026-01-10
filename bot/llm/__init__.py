"""LLM abstraction layer.

This module provides a provider-agnostic interface for LLM interactions.
All business logic should import from this module only.

Example:
    from llm import create_router_client, create_summarizer_client

    router = create_router_client()
    response = await router.complete(
        system_prompt="You are a classifier...",
        user_prompt="Classify this text...",
        model=os.getenv("ROUTER_LLM_MODEL"),
        temperature=0.1,
    )
"""

from .base import LLMClient
from .factory import create_llm_client, create_router_client, create_summarizer_client
from .exceptions import LLMError, LLMConfigurationError, LLMAPIError, LLMResponseError

__all__ = [
    # Base interface
    "LLMClient",
    # Factory functions
    "create_llm_client",
    "create_router_client",
    "create_summarizer_client",
    # Exceptions
    "LLMError",
    "LLMConfigurationError",
    "LLMAPIError",
    "LLMResponseError",
]
