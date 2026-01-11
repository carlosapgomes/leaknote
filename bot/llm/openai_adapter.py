"""OpenAI-compatible API adapter.

Works with:
- OpenAI API
- Ollama (http://localhost:11434/v1)
- vLLM
- LiteLLM proxy
- Together AI
- Groq
- Mistral
- DeepSeek
- Z.AI (GLM-4)
- OpenRouter (https://openrouter.ai/api/v1)
- Any OpenAI-compatible endpoint
"""

import asyncio
import httpx
import logging
from typing import Optional

from . import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2


class OpenAIAdapter(LLMClient):
    """Adapter for OpenAI-compatible APIs."""

    def __init__(
        self,
        api_url: str,
        api_key: str,
        model: str,
        default_max_tokens: int = 1000,
        timeout: float = 60.0,
    ):
        """
        Initialize the OpenAI adapter.

        Args:
            api_url: Base URL for the API (e.g., https://api.openai.com/v1)
            api_key: API key for authentication
            model: Model identifier (e.g., gpt-4, glm-4, anthropic/claude-sonnet-4)
            default_max_tokens: Default max tokens if not specified
            timeout: Request timeout in seconds
        """
        # Normalize URL - remove trailing slash, ensure we have /chat/completions
        self.api_url = api_url.rstrip("/")
        if not self.api_url.endswith("/chat/completions"):
            self.api_url = f"{self.api_url}/chat/completions"

        self.api_key = api_key
        self.model = model
        self.default_max_tokens = default_max_tokens
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "openai"

    async def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = None,
    ) -> LLMResponse:
        """Generate a completion using OpenAI-compatible API."""

        if max_tokens is None:
            max_tokens = self.default_max_tokens

        # Build messages
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        # Build request body
        # GPT-5+ models use max_completion_tokens, older models use max_tokens
        body = {
            "model": self.model,
            "messages": messages,
        }

        # Check if this is a GPT-5 or o-series model
        is_gpt5_or_o_model = (
            self.model.startswith("gpt-5") or
            self.model.startswith("o1") or
            self.model.startswith("o3")
        )

        # GPT-5 and o-series models have restrictions:
        # - Use max_completion_tokens instead of max_tokens
        # - Only support temperature=1 (default), so omit the parameter
        # - Use reasoning models that consume tokens for thinking, so we need more tokens
        if is_gpt5_or_o_model:
            # Reasoning models need significantly more tokens since they use
            # reasoning tokens + completion tokens. Set a higher limit.
            body["max_completion_tokens"] = max(2000, max_tokens * 4)
            # Only set temperature if it's 1 (the default)
            if temperature != 1.0:
                logger.warning(
                    f"Model {self.model} only supports temperature=1. "
                    f"Requested temperature {temperature} will be ignored."
                )
        else:
            body["max_tokens"] = max_tokens
            body["temperature"] = temperature

        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )
                    response.raise_for_status()

                    data = response.json()

                    # Extract content from OpenAI format
                    content = data["choices"][0]["message"]["content"]

                    # Extract usage if present
                    usage = data.get("usage")

                    return LLMResponse(
                        content=content,
                        model=data.get("model", self.model),
                        provider=self.provider_name,
                        usage=usage,
                        raw_response=data,
                    )

            except httpx.TimeoutException as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

            except httpx.HTTPStatusError as e:
                # Log the error details for debugging
                error_body = None
                try:
                    error_body = e.response.json()
                except Exception:
                    error_body = e.response.text

                logger.error(f"HTTP Error {e.response.status_code}: {error_body}")

                # Retry on server errors, raise on client errors
                if e.response.status_code >= 500:
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise Exception(f"API Error {e.response.status_code}: {error_body}") from e

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        raise last_error
