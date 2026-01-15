"""Claude API client with vision support for activity summarization."""

from __future__ import annotations

import asyncio
import base64
import json
import logging
from pathlib import Path
from typing import Any

import anthropic
from anthropic import AsyncAnthropic, APIError, RateLimitError

from captains_log.ai.prompts import SUMMARY_SYSTEM_PROMPT, format_five_minute_prompt
from captains_log.ai.schemas import SummaryResponse, ActivityType

logger = logging.getLogger(__name__)


class ClaudeClient:
    """Async Claude API client with vision support and rate limiting."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-haiku-4-5-20241022",
        max_tokens: int = 1024,
        max_retries: int = 3,
        base_delay: float = 1.0,
    ):
        """Initialize the Claude client.

        Args:
            api_key: Claude API key. If None, uses ANTHROPIC_API_KEY env var.
            model: Model to use (default: claude-haiku-4-5-20241022).
            max_tokens: Maximum tokens in response.
            max_retries: Maximum retry attempts on rate limit.
            base_delay: Base delay for exponential backoff.
        """
        self.model = model
        self.max_tokens = max_tokens
        self.max_retries = max_retries
        self.base_delay = base_delay

        # Initialize client (uses ANTHROPIC_API_KEY if api_key is None)
        self._client = AsyncAnthropic(api_key=api_key) if api_key else AsyncAnthropic()

        # Track usage
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._request_count = 0

    @property
    def total_input_tokens(self) -> int:
        """Total input tokens used."""
        return self._total_input_tokens

    @property
    def total_output_tokens(self) -> int:
        """Total output tokens used."""
        return self._total_output_tokens

    @property
    def request_count(self) -> int:
        """Total API requests made."""
        return self._request_count

    async def summarize_activity(
        self,
        activity_data: list[dict[str, Any]],
        period_start: str,
        period_end: str,
        context_switches: int,
        focus_hint: int,
        screenshot_path: Path | None = None,
    ) -> tuple[SummaryResponse, dict[str, int]]:
        """Generate a summary for activity data.

        Args:
            activity_data: List of activity events.
            period_start: ISO format start time.
            period_end: ISO format end time.
            context_switches: Number of app switches.
            focus_hint: Pre-calculated focus score hint.
            screenshot_path: Optional path to screenshot file.

        Returns:
            Tuple of (SummaryResponse, token_usage_dict).

        Raises:
            APIError: If API call fails after retries.
        """
        has_screenshot = screenshot_path is not None and screenshot_path.exists()

        # Format prompt
        prompt = format_five_minute_prompt(
            activity_data=activity_data,
            period_start=period_start,
            period_end=period_end,
            context_switches=context_switches,
            focus_hint=focus_hint,
            has_screenshot=has_screenshot,
        )

        # Build messages
        messages = self._build_messages(prompt, screenshot_path)

        # Make API call with retry logic
        response_text, usage = await self._call_api_with_retry(messages)

        # Parse response
        summary = self._parse_summary_response(response_text)

        return summary, usage

    def _build_messages(
        self, prompt: str, screenshot_path: Path | None = None
    ) -> list[dict[str, Any]]:
        """Build messages for API call, optionally including image."""
        content: list[dict[str, Any]] = []

        # Add screenshot if provided
        if screenshot_path and screenshot_path.exists():
            try:
                image_data = self._encode_image(screenshot_path)
                if image_data:
                    # Determine media type
                    suffix = screenshot_path.suffix.lower()
                    media_types = {
                        ".png": "image/png",
                        ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg",
                        ".webp": "image/webp",
                        ".gif": "image/gif",
                    }
                    media_type = media_types.get(suffix, "image/webp")

                    content.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_data,
                        },
                    })
            except Exception as e:
                logger.warning(f"Failed to encode screenshot: {e}")

        # Add text prompt
        content.append({"type": "text", "text": prompt})

        return [{"role": "user", "content": content}]

    def _encode_image(self, image_path: Path) -> str | None:
        """Encode image to base64."""
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()

            # Check size (Claude has limits)
            max_size = 20 * 1024 * 1024  # 20MB limit
            if len(image_bytes) > max_size:
                logger.warning(f"Image too large ({len(image_bytes)} bytes), skipping")
                return None

            return base64.b64encode(image_bytes).decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return None

    async def _call_api_with_retry(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str, dict[str, int]]:
        """Call API with exponential backoff retry on rate limits."""
        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self._client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    system=SUMMARY_SYSTEM_PROMPT,
                    messages=messages,
                )

                # Track usage
                usage = {
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                }
                self._total_input_tokens += usage["input_tokens"]
                self._total_output_tokens += usage["output_tokens"]
                self._request_count += 1

                # Extract text content
                text_content = ""
                for block in response.content:
                    if hasattr(block, "text"):
                        text_content += block.text

                logger.debug(
                    f"API call successful: {usage['input_tokens']} in, "
                    f"{usage['output_tokens']} out"
                )

                return text_content, usage

            except RateLimitError as e:
                last_error = e
                delay = self.base_delay * (2 ** attempt)
                logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)

            except APIError as e:
                last_error = e
                if e.status_code and e.status_code >= 500:
                    # Server error, retry
                    delay = self.base_delay * (2 ** attempt)
                    logger.warning(f"Server error, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    # Client error, don't retry
                    raise

        # All retries exhausted
        raise last_error or APIError("Max retries exceeded")

    def _parse_summary_response(self, response_text: str) -> SummaryResponse:
        """Parse Claude's response into SummaryResponse."""
        try:
            # Clean up response text
            text = response_text.strip()

            # Handle markdown code blocks
            if text.startswith("```json"):
                text = text[7:]
            elif text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]

            text = text.strip()

            # Parse JSON
            data = json.loads(text)

            # Validate activity_type
            activity_type = data.get("activity_type", "unknown").lower()
            try:
                activity_type = ActivityType(activity_type)
            except ValueError:
                activity_type = ActivityType.UNKNOWN

            return SummaryResponse(
                primary_app=data.get("primary_app", "Unknown"),
                activity_type=activity_type,
                focus_score=max(1, min(10, int(data.get("focus_score", 5)))),
                key_activities=data.get("key_activities", [])[:5],
                context=data.get("context", "No context available"),
                context_switches=max(0, int(data.get("context_switches", 0))),
                tags=data.get("tags", [])[:5],
                project_detected=data.get("project_detected"),
                meeting_detected=data.get("meeting_detected"),
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse summary response: {e}")
            logger.debug(f"Response text: {response_text[:500]}")
            # Return a default response
            return self._get_fallback_response()

    def _get_fallback_response(self) -> SummaryResponse:
        """Get a fallback response when parsing fails."""
        return SummaryResponse(
            primary_app="Unknown",
            activity_type=ActivityType.UNKNOWN,
            focus_score=5,
            key_activities=["Activity data could not be analyzed"],
            context="Failed to generate summary from API response",
            context_switches=0,
            tags=[],
        )

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics."""
        return {
            "total_input_tokens": self._total_input_tokens,
            "total_output_tokens": self._total_output_tokens,
            "request_count": self._request_count,
            "estimated_cost_usd": self._estimate_cost(),
        }

    def _estimate_cost(self) -> float:
        """Estimate cost based on token usage (Haiku pricing)."""
        # Haiku pricing as of 2024 (per million tokens)
        input_price = 0.25 / 1_000_000  # $0.25 per million input tokens
        output_price = 1.25 / 1_000_000  # $1.25 per million output tokens

        input_cost = self._total_input_tokens * input_price
        output_cost = self._total_output_tokens * output_price

        return input_cost + output_cost

    def reset_usage_stats(self) -> None:
        """Reset usage statistics."""
        self._total_input_tokens = 0
        self._total_output_tokens = 0
        self._request_count = 0


# Module-level client instance (lazily initialized)
_client: ClaudeClient | None = None


def get_claude_client(
    api_key: str | None = None,
    model: str | None = None,
) -> ClaudeClient:
    """Get or create the Claude client singleton."""
    global _client

    if _client is None:
        from captains_log.core.config import get_config

        config = get_config()
        _client = ClaudeClient(
            api_key=api_key or config.claude_api_key,
            model=model or config.summarization.model,
            max_tokens=config.summarization.max_tokens,
        )

    return _client
