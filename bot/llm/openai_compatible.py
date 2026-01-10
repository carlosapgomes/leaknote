"""OpenAI-compatible LLM adapter."""

import httpx

from .base import LLMClient
from .exceptions import LLMConfigurationError, LLMAPIError, LLMResponseError


class OpenAICompatibleClient(LLMClient):
    """
    OpenAI-compatible HTTP adapter.

    Works with any provider implementing the OpenAI API spec:
    - OpenAI
    - OpenRouter
    - Together AI
    - Custom OpenAI-compatible endpoints
    """

    def __init__(self, api_key: str, base_url: str, timeout: float = 60.0):
        """
        Initialize the OpenAI-compatible client.

        Args:
            api_key: API key for authentication
            base_url: Base URL of the OpenAI-compatible API
            timeout: Request timeout in seconds
        """
        if not api_key:
            raise LLMConfigurationError("OPENAI_API_KEY is required")
        if not base_url:
            raise LLMConfigurationError("OPENAI_BASE_URL is required")

        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

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
        Generate a completion using the OpenAI-compatible API.

        Args:
            system_prompt: Optional system prompt
            user_prompt: The user prompt/question
            model: Model identifier
            temperature: Sampling temperature (0.0-1.0)
            max_tokens: Maximum tokens to generate

        Returns:
            The generated text response
        """
        # Build messages
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": user_prompt})

        # Make request
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    },
                )
                response.raise_for_status()

        except httpx.TimeoutException as e:
            raise LLMAPIError(f"Request timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            raise LLMAPIError(
                f"API request failed: {e.response.text}",
                status_code=e.response.status_code,
            ) from e
        except httpx.RequestError as e:
            raise LLMAPIError(f"Request failed: {e}") from e

        # Parse response
        try:
            result = response.json()
            content = result["choices"][0]["message"]["content"]
            return content
        except (KeyError, IndexError) as e:
            raise LLMResponseError(f"Invalid response format: {e}") from e
