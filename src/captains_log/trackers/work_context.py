"""Deep work context extraction from URLs and window titles.

Extracts meaningful work context like:
- Which specific document you're editing
- Which meeting you're in
- Which GitHub repo/PR/issue you're viewing
- Which Slack channel/thread you're reading
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger(__name__)


@dataclass
class WorkContext:
    """Rich work context extracted from URL and window title."""

    # Basic info
    category: str  # Development, Communication, Meeting, Document, etc.
    service: str   # github, google-docs, slack, zoom, etc.

    # Specific context
    project: str | None = None      # Project/repo name
    document: str | None = None     # Document/file name
    meeting: str | None = None      # Meeting name
    channel: str | None = None      # Slack/Discord channel
    issue_id: str | None = None     # Issue/PR/ticket number

    # For organization mapping
    organization: str | None = None  # GitHub org, Slack workspace

    # Raw data
    url: str | None = None
    title: str | None = None

    # Confidence score (0-1)
    confidence: float = 1.0

    def to_dict(self) -> dict:
        """Convert to dictionary for storage."""
        return {
            "category": self.category,
            "service": self.service,
            "project": self.project,
            "document": self.document,
            "meeting": self.meeting,
            "channel": self.channel,
            "issue_id": self.issue_id,
            "organization": self.organization,
            "confidence": self.confidence,
        }

    @property
    def summary(self) -> str:
        """Human-readable summary of the work context."""
        if self.meeting:
            return f"Meeting: {self.meeting}"
        if self.document:
            return f"{self.service}: {self.document}"
        if self.project and self.issue_id:
            return f"{self.project} #{self.issue_id}"
        if self.project:
            return f"{self.service}: {self.project}"
        if self.channel:
            return f"{self.service}: #{self.channel}"
        return self.service


class WorkContextExtractor:
    """Extracts rich work context from URLs and window titles."""

    def extract(self, url: str | None, window_title: str | None, app_name: str | None = None) -> WorkContext:
        """Extract work context from URL and window title.

        Args:
            url: The browser URL (if available)
            window_title: The window title
            app_name: The application name

        Returns:
            WorkContext with extracted information
        """
        if url:
            context = self._extract_from_url(url, window_title)
            if context:
                context.url = url
                context.title = window_title
                return context

        # Fall back to window title parsing
        if window_title:
            context = self._extract_from_title(window_title, app_name)
            context.title = window_title
            return context

        return WorkContext(
            category="Other",
            service=app_name or "unknown",
            confidence=0.5,
        )

    def _extract_from_url(self, url: str, title: str | None) -> WorkContext | None:
        """Extract context from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path
            query = parse_qs(parsed.query)

            # Remove www prefix
            if domain.startswith("www."):
                domain = domain[4:]

            # Google Services
            if "google.com" in domain:
                return self._parse_google(domain, path, query, title)

            # GitHub
            if "github.com" in domain:
                return self._parse_github(path, title)

            # GitLab
            if "gitlab.com" in domain:
                return self._parse_gitlab(path, title)

            # Slack
            if "slack.com" in domain or "app.slack.com" in domain:
                return self._parse_slack(path, title)

            # Notion
            if "notion.so" in domain:
                return self._parse_notion(path, title)

            # Linear
            if "linear.app" in domain:
                return self._parse_linear(path, title)

            # Figma
            if "figma.com" in domain:
                return self._parse_figma(path, title)

            # Zoom
            if "zoom.us" in domain:
                return self._parse_zoom(path, title)

            # Jira
            if "atlassian.net" in domain and "jira" in domain:
                return self._parse_jira(path, title)

        except Exception as e:
            logger.debug(f"Error parsing URL {url}: {e}")

        return None

    def _parse_google(self, domain: str, path: str, query: dict, title: str | None) -> WorkContext:
        """Parse Google services URLs."""

        # Google Meet
        if "meet.google.com" in domain:
            meeting_name = self._extract_meeting_name(title)
            return WorkContext(
                category="Meeting",
                service="google-meet",
                meeting=meeting_name,
                confidence=0.9 if meeting_name else 0.7,
            )

        # Google Docs
        if "docs.google.com" in domain:
            doc_type = "document"
            if "/spreadsheets/" in path:
                doc_type = "spreadsheet"
            elif "/presentation/" in path:
                doc_type = "presentation"
            elif "/forms/" in path:
                doc_type = "form"

            doc_name = self._extract_doc_name(title, doc_type)
            return WorkContext(
                category="Document",
                service=f"google-{doc_type}",
                document=doc_name,
                confidence=0.9 if doc_name else 0.6,
            )

        # Google Drive
        if "drive.google.com" in domain:
            folder_name = self._extract_folder_name(title)
            return WorkContext(
                category="Productivity",
                service="google-drive",
                document=folder_name,
                confidence=0.7,
            )

        # Gmail
        if "mail.google.com" in domain:
            # Try to extract email subject from title
            subject = self._extract_email_subject(title)
            return WorkContext(
                category="Communication",
                service="gmail",
                document=subject,  # Using document field for email subject
                confidence=0.8 if subject else 0.6,
            )

        # Google Calendar
        if "calendar.google.com" in domain:
            return WorkContext(
                category="Productivity",
                service="google-calendar",
                confidence=0.8,
            )

        return WorkContext(
            category="Productivity",
            service="google",
            confidence=0.5,
        )

    def _parse_github(self, path: str, title: str | None) -> WorkContext:
        """Parse GitHub URLs."""
        parts = path.strip("/").split("/")

        if len(parts) >= 2:
            org = parts[0]
            repo = parts[1]
            project = f"{org}/{repo}"

            # Pull Request
            if len(parts) >= 4 and parts[2] == "pull":
                pr_num = parts[3]
                pr_title = self._extract_pr_title(title)
                return WorkContext(
                    category="Development",
                    service="github",
                    organization=org,
                    project=project,
                    issue_id=f"PR#{pr_num}",
                    document=pr_title,
                    confidence=0.95,
                )

            # Issue
            if len(parts) >= 4 and parts[2] == "issues":
                issue_num = parts[3]
                issue_title = self._extract_issue_title(title)
                return WorkContext(
                    category="Development",
                    service="github",
                    organization=org,
                    project=project,
                    issue_id=f"#{issue_num}",
                    document=issue_title,
                    confidence=0.95,
                )

            # Code file
            if len(parts) >= 4 and parts[2] == "blob":
                file_path = "/".join(parts[4:]) if len(parts) > 4 else None
                return WorkContext(
                    category="Development",
                    service="github",
                    organization=org,
                    project=project,
                    document=file_path,
                    confidence=0.9,
                )

            # Repository root
            return WorkContext(
                category="Development",
                service="github",
                organization=org,
                project=project,
                confidence=0.85,
            )

        return WorkContext(
            category="Development",
            service="github",
            confidence=0.6,
        )

    def _parse_gitlab(self, path: str, title: str | None) -> WorkContext:
        """Parse GitLab URLs."""
        parts = path.strip("/").split("/")

        if len(parts) >= 2:
            # GitLab can have nested groups
            if "-" in parts:
                dash_idx = parts.index("-")
                project = "/".join(parts[:dash_idx])
                action_type = parts[dash_idx + 1] if len(parts) > dash_idx + 1 else None

                if action_type == "merge_requests":
                    mr_num = parts[dash_idx + 2] if len(parts) > dash_idx + 2 else None
                    return WorkContext(
                        category="Development",
                        service="gitlab",
                        project=project,
                        issue_id=f"MR!{mr_num}" if mr_num else None,
                        confidence=0.9,
                    )
                if action_type == "issues":
                    issue_num = parts[dash_idx + 2] if len(parts) > dash_idx + 2 else None
                    return WorkContext(
                        category="Development",
                        service="gitlab",
                        project=project,
                        issue_id=f"#{issue_num}" if issue_num else None,
                        confidence=0.9,
                    )

            return WorkContext(
                category="Development",
                service="gitlab",
                project="/".join(parts[:2]),
                confidence=0.7,
            )

        return WorkContext(
            category="Development",
            service="gitlab",
            confidence=0.5,
        )

    def _parse_slack(self, path: str, title: str | None) -> WorkContext:
        """Parse Slack URLs and extract channel/thread info."""
        channel = None
        workspace = None

        # Extract workspace from title like "Threads - HyperVerge - Slack"
        if title:
            # Pattern: "Something - Workspace - Slack"
            match = re.search(r"(.+?)\s*-\s*(.+?)\s*-\s*Slack", title)
            if match:
                channel = match.group(1).strip()
                workspace = match.group(2).strip()
            elif " - Slack" in title:
                channel = title.replace(" - Slack", "").strip()

        # Try to extract from URL path
        parts = path.strip("/").split("/")
        if len(parts) >= 2 and parts[0] == "client":
            workspace = parts[1] if len(parts) > 1 else None

        return WorkContext(
            category="Communication",
            service="slack",
            organization=workspace,
            channel=channel,
            confidence=0.85 if channel else 0.6,
        )

    def _parse_notion(self, path: str, title: str | None) -> WorkContext:
        """Parse Notion URLs."""
        doc_name = None
        if title:
            # Notion titles are usually "Page Name - Notion"
            doc_name = title.replace(" - Notion", "").strip()

        return WorkContext(
            category="Productivity",
            service="notion",
            document=doc_name,
            confidence=0.85 if doc_name else 0.6,
        )

    def _parse_linear(self, path: str, title: str | None) -> WorkContext:
        """Parse Linear URLs."""
        parts = path.strip("/").split("/")

        # Linear URLs: /team/issue-id or /project/issue-id
        issue_id = None
        project = None

        for i, part in enumerate(parts):
            if re.match(r"^[A-Z]+-\d+$", part):  # Issue ID like "ENG-123"
                issue_id = part
            elif part == "issue" and i + 1 < len(parts):
                issue_id = parts[i + 1]
            elif part == "project" and i + 1 < len(parts):
                project = parts[i + 1]

        # Extract issue title from window title
        issue_title = None
        if title:
            # Linear titles: "Issue Title - Linear"
            issue_title = title.replace(" - Linear", "").strip()

        return WorkContext(
            category="Development",
            service="linear",
            project=project,
            issue_id=issue_id,
            document=issue_title,
            confidence=0.9 if issue_id else 0.7,
        )

    def _parse_figma(self, path: str, title: str | None) -> WorkContext:
        """Parse Figma URLs."""
        _parts = path.strip("/").split("/")  # noqa: F841 - reserved for future use

        doc_name = None
        if title:
            # Figma titles: "File Name - Figma"
            doc_name = title.replace(" - Figma", "").replace(" – Figma", "").strip()

        file_type = "design"
        if "/file/" in path:
            file_type = "design"
        elif "/proto/" in path:
            file_type = "prototype"
        elif "/figjam/" in path:
            file_type = "figjam"

        return WorkContext(
            category="Design",
            service=f"figma-{file_type}",
            document=doc_name,
            confidence=0.85 if doc_name else 0.6,
        )

    def _parse_zoom(self, path: str, title: str | None) -> WorkContext:
        """Parse Zoom URLs."""
        meeting_name = self._extract_meeting_name(title)

        # Check if in a meeting
        if "/j/" in path or "/wc/" in path:
            return WorkContext(
                category="Meeting",
                service="zoom",
                meeting=meeting_name,
                confidence=0.9 if meeting_name else 0.7,
            )

        return WorkContext(
            category="Meeting",
            service="zoom",
            confidence=0.6,
        )

    def _parse_jira(self, path: str, title: str | None) -> WorkContext:
        """Parse Jira URLs."""
        parts = path.strip("/").split("/")

        issue_id = None
        project = None

        # Jira URLs: /browse/PROJ-123
        if "browse" in parts:
            idx = parts.index("browse")
            if idx + 1 < len(parts):
                issue_id = parts[idx + 1]
                if "-" in issue_id:
                    project = issue_id.split("-")[0]

        issue_title = None
        if title and issue_id:
            # Jira titles: "[PROJ-123] Issue Title - Jira"
            match = re.search(r"\[" + re.escape(issue_id) + r"\]\s*(.+?)\s*-\s*Jira", title)
            if match:
                issue_title = match.group(1)

        return WorkContext(
            category="Development",
            service="jira",
            project=project,
            issue_id=issue_id,
            document=issue_title,
            confidence=0.9 if issue_id else 0.6,
        )

    def _extract_from_title(self, title: str, app_name: str | None) -> WorkContext:
        """Extract context from window title when URL is not available."""

        # Meeting detection from title
        meeting_keywords = ["meeting", "call", "standup", "sync", "1:1", "interview", "demo"]
        title_lower = title.lower()

        if any(kw in title_lower for kw in meeting_keywords):
            return WorkContext(
                category="Meeting",
                service=app_name or "unknown",
                meeting=title,
                confidence=0.7,
            )

        # Slack detection
        if "slack" in title_lower:
            # Parse Slack title format
            match = re.search(r"(.+?)\s*-\s*(.+?)\s*-\s*Slack", title, re.IGNORECASE)
            if match:
                return WorkContext(
                    category="Communication",
                    service="slack",
                    channel=match.group(1).strip(),
                    organization=match.group(2).strip(),
                    confidence=0.85,
                )

        return WorkContext(
            category="Other",
            service=app_name or "unknown",
            document=title,
            confidence=0.5,
        )

    # Helper methods for extracting specific information

    def _extract_meeting_name(self, title: str | None) -> str | None:
        """Extract meeting name from window title."""
        if not title:
            return None

        # Google Meet: "Meeting Name - Google Meet"
        if "Google Meet" in title:
            name = title.replace("- Google Meet", "").strip()
            if name and name != "Meet":
                return name

        # Zoom: "Zoom Meeting" or "Meeting Name - Zoom"
        if "Zoom" in title:
            name = title.replace("- Zoom", "").replace("Zoom Meeting", "").strip()
            if name:
                return name

        return title

    def _extract_doc_name(self, title: str | None, doc_type: str) -> str | None:
        """Extract document name from window title."""
        if not title:
            return None

        # Google Docs: "Document Name - Google Docs"
        # Google Sheets: "Spreadsheet Name - Google Sheets"
        suffixes = [
            "- Google Docs",
            "- Google Sheets",
            "- Google Slides",
            "- Google Forms",
        ]

        for suffix in suffixes:
            if suffix in title:
                name = title.replace(suffix, "").strip()
                if name and name != "Untitled":
                    return name

        return None

    def _extract_folder_name(self, title: str | None) -> str | None:
        """Extract folder name from Google Drive title."""
        if not title:
            return None

        # "Folder Name - Google Drive"
        if "- Google Drive" in title:
            name = title.replace("- Google Drive", "").strip()
            if name and name != "My Drive":
                return name

        return None

    def _extract_email_subject(self, title: str | None) -> str | None:
        """Extract email subject from Gmail title."""
        if not title:
            return None

        # Gmail: "Subject - email@gmail.com - Gmail"
        # Or: "Inbox - Gmail"
        if "Gmail" in title:
            # Remove Gmail suffix
            name = re.sub(r"\s*-\s*[^-]+@[^-]+\s*-\s*Gmail$", "", title)
            name = name.replace("- Gmail", "").strip()
            if name and name not in ["Inbox", "Compose", "Sent"]:
                return name

        return None

    def _extract_pr_title(self, title: str | None) -> str | None:
        """Extract PR title from GitHub window title."""
        if not title:
            return None

        # GitHub PR: "PR Title by author · Pull Request #123 · org/repo"
        match = re.search(r"^(.+?)\s+by\s+\w+\s+·\s+Pull Request", title)
        if match:
            return match.group(1).strip()

        return None

    def _extract_issue_title(self, title: str | None) -> str | None:
        """Extract issue title from GitHub window title."""
        if not title:
            return None

        # GitHub Issue: "Issue Title · Issue #123 · org/repo"
        match = re.search(r"^(.+?)\s+·\s+Issue\s+#\d+", title)
        if match:
            return match.group(1).strip()

        return None


# Singleton instance
_extractor: WorkContextExtractor | None = None


def get_work_context_extractor() -> WorkContextExtractor:
    """Get the singleton work context extractor."""
    global _extractor
    if _extractor is None:
        _extractor = WorkContextExtractor()
    return _extractor


def extract_work_context(url: str | None, title: str | None, app: str | None = None) -> WorkContext:
    """Convenience function to extract work context."""
    return get_work_context_extractor().extract(url, title, app)
