"""Anthropic API adapter.

For direct Claude API access. Use this when you need Anthropic-specific features
or when using the native Anthropic API.

For most use cases, the OpenAI adapter with OpenRouter works fine for Claude models.
"""

import asyncio
import httpx
from typing import Optional

from . import LLMClient, LLMResponse


# Retry settings
MAX_RETRIES = 3
RETRY_DELAY = 2


class AnthropicAdapter(LLMClient):
    """Adapter for native Anthropic API."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        api_url: str = "https://api.anthropic.com/v1/messages",
        api_version: str = "2023-06-01",
        default_max_tokens: int = 1000,
        timeout: float = 60.0,
    ):
        """
        Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key
            model: Model identifier (e.g., claude-sonnet-4-20250514)
            api_url: API endpoint URL
            api_version: Anthropic API version
            default_max_tokens: Default max tokens if not specified
            timeout: Request timeout in seconds
        """
        self.api_key = api_key
        self.model = model
        self.api_url = api_url
        self.api_version = api_version
        self.default_max_tokens = default_max_tokens
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "anthropic"

    async def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = None,
    ) -> LLMResponse:
        """Generate a completion using Anthropic API."""

        if max_tokens is None:
            max_tokens = self.default_max_tokens

        # Build request body (Anthropic format)
        body = {
            "model": self.model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }

        if system:
            body["system"] = system

        if temperature != 0.7:  # Only include if non-default
            body["temperature"] = temperature

        last_error = None

        for attempt in range(MAX_RETRIES):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(
                        self.api_url,
                        headers={
                            "x-api-key": self.api_key,
                            "anthropic-version": self.api_version,
                            "Content-Type": "application/json",
                        },
                        json=body,
                    )
                    response.raise_for_status()

                    data = response.json()

                    # Extract content from Anthropic format
                    # Response has content array with text blocks
                    content_blocks = data.get("content", [])
                    content = ""
                    for block in content_blocks:
                        if block.get("type") == "text":
                            content += block.get("text", "")

                    # Extract usage
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
                if e.response.status_code >= 500:
                    last_error = e
                    if attempt < MAX_RETRIES - 1:
                        await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                else:
                    raise

            except Exception as e:
                last_error = e
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))

        raise last_error
