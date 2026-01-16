"""Screenshot analysis using Claude Haiku vision."""

from __future__ import annotations

import base64
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image

# Load .env file from project root
_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
    logging.getLogger(__name__).debug(f"Loaded .env from {_env_path}")

logger = logging.getLogger(__name__)

# Max dimension for analysis (keep small to reduce cost)
MAX_ANALYSIS_WIDTH = 800
MAX_ANALYSIS_HEIGHT = 600
JPEG_QUALITY = 60


def compress_for_analysis(image_path: Path) -> tuple[str, str]:
    """Compress screenshot for API analysis.

    Returns (base64_data, media_type).
    Target: ~30-50KB to minimize API costs.
    """
    with Image.open(image_path) as img:
        # Convert to RGB if needed (WebP might have alpha)
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')

        # Resize to max dimensions
        img.thumbnail((MAX_ANALYSIS_WIDTH, MAX_ANALYSIS_HEIGHT), Image.Resampling.LANCZOS)

        # Save as JPEG with low quality
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        buffer.seek(0)

        data = base64.standard_b64encode(buffer.read()).decode('utf-8')
        size_kb = len(data) * 3 / 4 / 1024  # Approximate decoded size
        logger.debug(f"Compressed screenshot: {size_kb:.1f}KB")

        return data, "image/jpeg"


async def analyze_screenshot(
    image_path: Path,
    app_name: str | None = None,
    window_title: str | None = None,
) -> dict[str, Any]:
    """Analyze a screenshot using Claude Haiku.

    Returns structured analysis with:
    - summary: Brief description of what's visible
    - activity_type: work, communication, browsing, entertainment, etc.
    - key_content: Main text/content visible (if any)
    - focus_indicator: productive, neutral, distraction
    """
    import anthropic

    if not image_path.exists():
        raise FileNotFoundError(f"Screenshot not found: {image_path}")

    # Compress the image
    image_data, media_type = compress_for_analysis(image_path)

    # Build context hint
    context = ""
    if app_name:
        context += f"App: {app_name}. "
    if window_title:
        context += f"Window: {window_title[:100]}. "

    prompt = f"""Analyze this screenshot briefly. {context}

Respond in this exact JSON format (no markdown):
{{"summary": "One sentence describing what's visible",
"activity_type": "work|communication|browsing|entertainment|system|other",
"key_content": "Main visible text/content in 10 words or less, or null",
"focus_indicator": "productive|neutral|distraction"}}"""

    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=200,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": image_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
        )

        # Parse response
        import json
        text = response.content[0].text.strip()

        # Handle potential markdown wrapping
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(text)
        result["model"] = "claude-haiku-20241022"
        result["tokens_used"] = response.usage.input_tokens + response.usage.output_tokens

        # Estimate cost (Haiku: $0.25/MTok input, $1.25/MTok output for images)
        input_cost = response.usage.input_tokens * 0.25 / 1_000_000
        output_cost = response.usage.output_tokens * 1.25 / 1_000_000
        result["estimated_cost"] = round(input_cost + output_cost, 6)

        logger.info(f"Screenshot analyzed: {result['activity_type']} - ${result['estimated_cost']:.4f}")
        return result

    except Exception as e:
        logger.error(f"Screenshot analysis failed: {e}")
        return {
            "summary": "Analysis failed",
            "activity_type": "unknown",
            "key_content": None,
            "focus_indicator": "neutral",
            "error": str(e),
        }


async def analyze_screenshot_batch(
    screenshots: list[tuple[Path, str | None, str | None]],
) -> list[dict[str, Any]]:
    """Analyze multiple screenshots.

    Args:
        screenshots: List of (path, app_name, window_title) tuples

    Returns:
        List of analysis results
    """
    results = []
    for path, app_name, window_title in screenshots:
        try:
            result = await analyze_screenshot(path, app_name, window_title)
            results.append(result)
        except Exception as e:
            logger.error(f"Failed to analyze {path}: {e}")
            results.append({"error": str(e)})
    return results
