"""Deep work analysis combining screenshots with activity context."""

from __future__ import annotations

import base64
import json
import logging
import re
from io import BytesIO
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from PIL import Image

# Load .env file from project root
_env_path = Path(__file__).parent.parent.parent.parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)

logger = logging.getLogger(__name__)

# Image compression settings
MAX_ANALYSIS_WIDTH = 1024  # Slightly larger for better OCR
MAX_ANALYSIS_HEIGHT = 768
JPEG_QUALITY = 70


# Work categories with subcategories
WORK_CATEGORIES = {
    "development": ["coding", "debugging", "code_review", "testing", "devops", "database"],
    "communication": ["email", "slack", "meeting", "video_call", "messaging"],
    "research": ["documentation", "stack_overflow", "github_browsing", "learning", "reading"],
    "writing": ["documentation", "notes", "blogging", "technical_writing"],
    "design": ["ui_design", "wireframing", "graphics", "prototyping"],
    "admin": ["calendar", "task_management", "file_management", "settings"],
    "entertainment": ["social_media", "video", "music", "gaming", "news"],
}

# Project detection patterns
PROJECT_PATTERNS = [
    # Git repo patterns in terminal/IDE
    r"(?:^|\s|/)([a-zA-Z][\w-]{2,30})(?:\s+[—-]|$)",  # "project-name —"
    r"(?:github\.com|gitlab\.com|bitbucket\.org)/[\w-]+/([\w-]+)",  # GitHub URLs
    r"(?:~/|/Users/\w+/|/home/\w+/)(?:[\w-]+/)*([\w-]+)(?:/|$)",  # File paths
]

# Technology detection patterns
TECH_PATTERNS = {
    "python": [r"\.py\b", r"python", r"pip", r"conda", r"pytest", r"django", r"flask", r"fastapi"],
    "javascript": [r"\.js\b", r"\.tsx?\b", r"node", r"npm", r"yarn", r"react", r"vue", r"next\.js"],
    "typescript": [r"\.tsx?\b", r"typescript", r"tsc"],
    "rust": [r"\.rs\b", r"cargo", r"rustc"],
    "go": [r"\.go\b", r"go\s+(build|run|test)"],
    "docker": [r"docker", r"dockerfile", r"container"],
    "kubernetes": [r"kubectl", r"k8s", r"kubernetes"],
    "sql": [r"\.sql\b", r"SELECT", r"INSERT", r"CREATE TABLE", r"sqlite", r"postgres", r"mysql"],
    "git": [r"\bgit\b", r"commit", r"branch", r"merge", r"rebase"],
    "terminal": [r"terminal", r"bash", r"zsh", r"shell"],
}


def compress_for_analysis(image_path: Path) -> tuple[str, str]:
    """Compress screenshot for API analysis."""
    with Image.open(image_path) as img:
        if img.mode in ('RGBA', 'P'):
            img = img.convert('RGB')
        img.thumbnail((MAX_ANALYSIS_WIDTH, MAX_ANALYSIS_HEIGHT), Image.Resampling.LANCZOS)
        buffer = BytesIO()
        img.save(buffer, format='JPEG', quality=JPEG_QUALITY, optimize=True)
        buffer.seek(0)
        data = base64.standard_b64encode(buffer.read()).decode('utf-8')
        return data, "image/jpeg"


def extract_project_from_context(
    window_title: str | None,
    url: str | None,
    app_name: str | None,
) -> str | None:
    """Extract project name from available context."""
    context = f"{window_title or ''} {url or ''}"

    # Try each pattern
    for pattern in PROJECT_PATTERNS:
        matches = re.findall(pattern, context, re.IGNORECASE)
        for match in matches:
            # Filter out common non-project names
            if match.lower() not in ["users", "home", "desktop", "documents", "downloads",
                                      "applications", "library", "var", "tmp", "etc"]:
                return match

    return None


def detect_technologies(
    window_title: str | None,
    url: str | None,
    key_content: str | None,
) -> list[str]:
    """Detect technologies from context."""
    context = f"{window_title or ''} {url or ''} {key_content or ''}".lower()
    detected = []

    for tech, patterns in TECH_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, context, re.IGNORECASE):
                detected.append(tech)
                break

    return detected


async def analyze_work_context(
    image_path: Path,
    app_name: str | None = None,
    window_title: str | None = None,
    url: str | None = None,
    recent_activities: list[dict] | None = None,
) -> dict[str, Any]:
    """Deep analysis of work context combining visual and metadata.

    Returns:
        - project: Detected project/repository name
        - category: Main work category
        - subcategory: Specific work type
        - technologies: List of detected technologies
        - task_description: What the user is working on
        - context_richness: How much context we could extract (0-100)
        - deep_work_score: Focus/depth indicator (0-100)
        - summary: Human-readable summary
    """
    import anthropic

    if not image_path.exists():
        raise FileNotFoundError(f"Screenshot not found: {image_path}")

    # Compress the image
    image_data, media_type = compress_for_analysis(image_path)

    # Build rich context for the prompt
    context_parts = []
    if app_name:
        context_parts.append(f"Application: {app_name}")
    if window_title:
        context_parts.append(f"Window title: {window_title[:200]}")
    if url:
        context_parts.append(f"URL: {url}")

    # Add recent activity context if available
    if recent_activities:
        recent_apps = list(set(a.get("app_name", "") for a in recent_activities[:5]))
        context_parts.append(f"Recent apps: {', '.join(recent_apps)}")

    context_str = "\n".join(context_parts) if context_parts else "No additional context"

    # Pre-extract what we can from metadata
    pre_project = extract_project_from_context(window_title, url, app_name)
    pre_technologies = detect_technologies(window_title, url, None)

    prompt = f"""Analyze this screenshot to understand what work is being done.

Context from system:
{context_str}

Pre-detected project hint: {pre_project or 'unknown'}
Pre-detected technologies: {', '.join(pre_technologies) if pre_technologies else 'none detected'}

Analyze the screenshot and respond with this exact JSON (no markdown):
{{
    "project": "project or repository name visible, or null if unclear",
    "category": "development|communication|research|writing|design|admin|entertainment|other",
    "subcategory": "specific work type like coding, debugging, email, slack, documentation, etc",
    "technologies": ["list", "of", "technologies", "visible"],
    "task_description": "One sentence describing the specific task being done",
    "visible_content": {{
        "file_or_document": "filename or document title if visible",
        "key_text": "most important text visible (20 words max)",
        "ui_elements": "notable UI elements like editor, terminal, browser tabs, etc"
    }},
    "deep_work_indicators": {{
        "single_focus": true/false (is user focused on one thing?),
        "complex_content": true/false (is the content complex/technical?),
        "active_editing": true/false (is user actively creating/editing?)
    }},
    "summary": "2-3 sentence summary of what work is happening"
}}

Be specific about the project if you can identify it from paths, URLs, or visible content.
For technologies, list specific frameworks/languages visible (React, Python, Docker, etc)."""

    client = anthropic.Anthropic()

    try:
        response = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=500,
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
        text = response.content[0].text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        result = json.loads(text)

        # Merge pre-detected data if AI didn't find anything
        if not result.get("project") and pre_project:
            result["project"] = pre_project
        if not result.get("technologies") and pre_technologies:
            result["technologies"] = pre_technologies

        # Calculate scores
        deep_work = result.get("deep_work_indicators", {})
        deep_work_score = sum([
            deep_work.get("single_focus", False) * 40,
            deep_work.get("complex_content", False) * 35,
            deep_work.get("active_editing", False) * 25,
        ])
        result["deep_work_score"] = deep_work_score

        # Calculate context richness
        context_richness = sum([
            bool(result.get("project")) * 25,
            bool(result.get("technologies")) * 20,
            bool(result.get("task_description")) * 20,
            bool(result.get("visible_content", {}).get("file_or_document")) * 20,
            bool(result.get("visible_content", {}).get("key_text")) * 15,
        ])
        result["context_richness"] = context_richness

        # Add metadata
        result["model"] = "claude-3-5-haiku-20241022"
        result["tokens_used"] = response.usage.input_tokens + response.usage.output_tokens
        input_cost = response.usage.input_tokens * 0.25 / 1_000_000
        output_cost = response.usage.output_tokens * 1.25 / 1_000_000
        result["estimated_cost"] = round(input_cost + output_cost, 6)

        # Simplified fields for backwards compatibility
        result["activity_type"] = result.get("category", "other")
        focus_map = {
            "development": "productive",
            "writing": "productive",
            "research": "productive",
            "design": "productive",
            "communication": "neutral",
            "admin": "neutral",
            "entertainment": "distraction",
        }
        result["focus_indicator"] = focus_map.get(result.get("category"), "neutral")
        result["key_content"] = result.get("visible_content", {}).get("key_text")

        logger.info(
            f"Work analyzed: {result.get('category')}/{result.get('subcategory')} "
            f"project={result.get('project')} deep_work={deep_work_score} "
            f"cost=${result['estimated_cost']:.4f}"
        )

        return result

    except Exception as e:
        logger.error(f"Work analysis failed: {e}")
        return {
            "summary": "Analysis failed",
            "category": "unknown",
            "subcategory": "unknown",
            "project": pre_project,
            "technologies": pre_technologies,
            "deep_work_score": 0,
            "context_richness": 0,
            "activity_type": "unknown",
            "focus_indicator": "neutral",
            "error": str(e),
        }


async def categorize_time_block(
    activities: list[dict],
    screenshots_analysis: list[dict],
) -> dict[str, Any]:
    """Categorize a block of time based on activities and screenshot analysis.

    Args:
        activities: List of activity log entries
        screenshots_analysis: List of analyzed screenshots

    Returns:
        Time categorization with project breakdown
    """
    # Aggregate projects
    projects = {}
    categories = {}
    technologies = set()

    for analysis in screenshots_analysis:
        project = analysis.get("project", "unknown")
        category = analysis.get("category", "other")

        projects[project] = projects.get(project, 0) + 1
        categories[category] = categories.get(category, 0) + 1
        technologies.update(analysis.get("technologies", []))

    # Also extract from activities
    for activity in activities:
        if activity.get("url"):
            # Try to extract project from URLs
            project = extract_project_from_context(
                activity.get("window_title"),
                activity.get("url"),
                activity.get("app_name"),
            )
            if project:
                projects[project] = projects.get(project, 0) + 1

    # Calculate primary focus
    primary_project = max(projects.items(), key=lambda x: x[1])[0] if projects else "unknown"
    primary_category = max(categories.items(), key=lambda x: x[1])[0] if categories else "other"

    # Calculate deep work percentage
    deep_work_count = sum(1 for a in screenshots_analysis if a.get("deep_work_score", 0) >= 60)
    deep_work_pct = (deep_work_count / len(screenshots_analysis) * 100) if screenshots_analysis else 0

    return {
        "primary_project": primary_project,
        "primary_category": primary_category,
        "projects": projects,
        "categories": categories,
        "technologies": list(technologies),
        "deep_work_percentage": round(deep_work_pct, 1),
        "activity_count": len(activities),
        "screenshot_count": len(screenshots_analysis),
    }
