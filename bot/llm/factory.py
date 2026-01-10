"""Factory for creating LLM clients from configuration."""

from typing import Literal

from . import LLMClient
from .openai_adapter import OpenAIAdapter
from .anthropic_adapter import AnthropicAdapter


ProviderType = Literal["openai", "anthropic"]


def create_client(
    provider: ProviderType,
    api_url: str,
    api_key: str,
    model: str,
    **kwargs,
) -> LLMClient:
    """
    Create an LLM client from configuration.

    Args:
        provider: Provider type ('openai' or 'anthropic')
        api_url: API endpoint URL
        api_key: API key
        model: Model identifier
        **kwargs: Additional provider-specific arguments

    Returns:
        Configured LLMClient instance

    Raises:
        ValueError: If provider is not supported
    """
    if provider == "openai":
        return OpenAIAdapter(
            api_url=api_url,
            api_key=api_key,
            model=model,
            **kwargs,
        )
    elif provider == "anthropic":
        return AnthropicAdapter(
            api_key=api_key,
            model=model,
            api_url=api_url,
            **kwargs,
        )
    else:
        raise ValueError(f"Unsupported provider: {provider}")


# Convenience functions for common configurations


def create_openai_client(api_key: str, model: str = "gpt-4o", **kwargs) -> LLMClient:
    """Create an OpenAI client."""
    return OpenAIAdapter(
        api_url="https://api.openai.com/v1",
        api_key=api_key,
        model=model,
        **kwargs,
    )


def create_anthropic_client(
    api_key: str, model: str = "claude-sonnet-4-20250514", **kwargs
) -> LLMClient:
    """Create an Anthropic client."""
    return AnthropicAdapter(
        api_key=api_key,
        model=model,
        **kwargs,
    )


def create_ollama_client(model: str = "llama3", base_url: str = None, **kwargs) -> LLMClient:
    """Create an Ollama client (local models)."""
    return OpenAIAdapter(
        api_url=base_url or "http://localhost:11434/v1",
        api_key="ollama",  # Ollama doesn't need a real key
        model=model,
        **kwargs,
    )


def create_openrouter_client(api_key: str, model: str, **kwargs) -> LLMClient:
    """Create an OpenRouter client."""
    return OpenAIAdapter(
        api_url="https://openrouter.ai/api/v1",
        api_key=api_key,
        model=model,
        **kwargs,
    )
