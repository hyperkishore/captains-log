"""AI module for Claude-powered activity summarization."""

from captains_log.ai.batch_processor import BatchProcessor
from captains_log.ai.claude_client import ClaudeClient
from captains_log.ai.schemas import ActivityType, SummaryResponse
from captains_log.ai.screenshot_analyzer import (
    analyze_screenshot,
    analyze_screenshot_batch,
    compress_for_analysis,
)

__all__ = [
    "SummaryResponse",
    "ActivityType",
    "ClaudeClient",
    "BatchProcessor",
    "analyze_screenshot",
    "analyze_screenshot_batch",
    "compress_for_analysis",
]
