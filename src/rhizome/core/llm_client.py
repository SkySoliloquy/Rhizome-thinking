"""Unified LLM API client with retry, caching, and error handling."""

import json
import logging
from typing import Any, Optional
from abc import ABC, abstractmethod

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from rhizome.config import settings

logger = logging.getLogger(__name__)


class LLMClient(ABC):
    """Base class for LLM API clients with common functionality."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        default_timeout: float = 60.0,
        max_retries: int = 3
    ):
        """Initialize LLM client.

        Args:
            api_key: API key (defaults to settings)
            base_url: API base URL (defaults to settings)
            model: Model name (defaults to settings)
            default_timeout: Default request timeout in seconds
            max_retries: Maximum number of retry attempts
        """
        self.api_key = api_key or settings.minimax_api_key
        self.base_url = base_url or settings.minimax_base_url
        self.model = model or settings.minimax_model
        self.default_timeout = default_timeout
        self.max_retries = max_retries

        if not self.api_key:
            raise ValueError(f"{self.__class__.__name__}: API key is required")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def call_api_async(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: Optional[float] = None
    ) -> dict[str, Any]:
        """Call LLM API asynchronously with retry logic.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout (uses default if not specified)

        Returns:
            API response dictionary

        Raises:
            httpx.HTTPError: If API call fails after retries
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        actual_timeout = timeout or self.default_timeout

        logger.debug(f"[{self.__class__.__name__}] Calling API: {url}")
        logger.debug(f"[{self.__class__.__name__}] Model: {self.model}, Timeout: {actual_timeout}s")

        async with httpx.AsyncClient(timeout=actual_timeout) as client:
            response = await client.post(url, headers=headers, json=payload)

            if not response.is_success:
                error_detail = response.text[:500]
                logger.error(f"[{self.__class__.__name__}] API error {response.status_code}: {error_detail}")
                raise httpx.HTTPStatusError(
                    f"API returned {response.status_code}: {error_detail}",
                    request=response.request,
                    response=response
                )

            return response.json()

    def call_api_sync(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 2000,
        timeout: Optional[float] = None
    ) -> dict[str, Any]:
        """Call LLM API synchronously with retry logic.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate
            timeout: Request timeout (uses default if not specified)

        Returns:
            API response dictionary
        """
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        actual_timeout = timeout or self.default_timeout

        logger.debug(f"[{self.__class__.__name__}] Calling API (sync): {url}")

        with httpx.Client(timeout=actual_timeout) as client:
            response = client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()

    def extract_content(self, response: dict[str, Any]) -> str:
        """Extract content from API response, handling multiple formats.

        Args:
            response: API response dictionary

        Returns:
            Extracted content string

        Raises:
            ValueError: If no content found in response
        """
        # Check for MiniMax error response
        base_resp = response.get("base_resp", {})
        if base_resp.get("status_code", 0) != 0:
            raise ValueError(f"API error: {base_resp.get('status_msg', 'Unknown error')}")

        # Try MiniMax format first
        content = response.get("reply", "")

        # Fallback to OpenAI format
        if not content:
            choices = response.get("choices", [])
            if choices:
                message = choices[0].get("message", {})
                content = message.get("content", "")

        if not content:
            raise ValueError("Empty content in API response")

        return content

    def parse_json_response(self, response: dict[str, Any]) -> dict[str, Any]:
        """Parse JSON from API response content.

        Handles JSON wrapped in markdown code blocks.

        Args:
            response: API response dictionary

        Returns:
            Parsed JSON dictionary

        Raises:
            ValueError: If JSON parsing fails
        """
        content = self.extract_content(response)

        # Extract JSON from markdown code blocks
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from response: {e}")

    @abstractmethod
    def process_response(self, response: dict[str, Any]) -> Any:
        """Process API response into domain-specific format.

        Subclasses must implement this to convert raw API response
        into their specific data structures.

        Args:
            response: Raw API response

        Returns:
            Processed result in domain-specific format
        """
        pass


class MockLLMClient(LLMClient):
    """Mock LLM client for testing without API calls."""

    def __init__(self):
        """Initialize mock client with placeholder values."""
        super().__init__(api_key="mock", base_url="mock", model="mock")

    async def call_api_async(self, messages, **kwargs):
        """Return mock response."""
        return {"reply": '{"mock": true}'}

    def call_api_sync(self, messages, **kwargs):
        """Return mock response."""
        return {"reply": '{"mock": true}'}

    def process_response(self, response):
        """Return mock processed response."""
        return {"mock": True}
