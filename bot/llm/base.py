"""Abstract base class for LLM providers."""

from abc import ABC, abstractmethod
from typing import Any


class LLMClient(ABC):
    """
    Abstract base class for LLM providers.

    All LLM interactions must go through this interface.
    """

    @abstractmethod
    async def complete(
        self,
        *,
        system_prompt: str | None = None,
        user_prompt: str,
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate a completion from the LLM.

        Args:
            system_prompt: Optional system prompt to set behavior
            user_prompt: The user prompt/question
            model: Model identifier
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text response

        Raises:
            LLMConfigurationError: Configuration is missing or invalid
            LLMAPIError: API call failed
            LLMResponseError: Response is invalid or cannot be parsed
        """
        pass
