"""LLM-specific exceptions."""


class LLMError(Exception):
    """Base exception for LLM-related errors."""

    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM configuration is missing or invalid."""

    pass


class LLMAPIError(LLMError):
    """Raised when LLM API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class LLMResponseError(LLMError):
    """Raised when LLM response is invalid or cannot be parsed."""

    pass
