"""LLM client interface and types."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any


@dataclass
class LLMResponse:
    """Response from an LLM completion."""
    
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, Any]] = None
    raw_response: Optional[Dict[str, Any]] = field(default=None, repr=False)


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'openai', 'anthropic')."""
        pass

    @abstractmethod
    async def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> LLMResponse:
        """
        Generate a text completion.

        Args:
            prompt: The user prompt
            system: Optional system prompt
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with the generated content
        """
        pass

    async def complete_json(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 1000,
    ) -> dict:
        """
        Generate a completion and parse as JSON.

        Args:
            prompt: The user prompt (should instruct model to return JSON)
            system: Optional system prompt
            temperature: Low temperature recommended for structured output
            max_tokens: Maximum tokens to generate

        Returns:
            Parsed JSON dict

        Raises:
            JSONDecodeError: If response is not valid JSON
        """
        import json

        response = await self.complete(
            prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        content = response.content.strip()

        # Handle markdown-wrapped JSON
        if content.startswith("```"):
            # Remove ```json or ``` prefix and ``` suffix
            lines = content.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            content = "\n".join(lines)

        return json.loads(content)
