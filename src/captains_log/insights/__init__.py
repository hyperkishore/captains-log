"""Insights and pattern detection for Captain's Log.

Analyzes historical activity data to surface focus patterns,
peak hours, context switch spikes, and weekly rhythms.
"""

from captains_log.insights.pattern_detector import FocusPattern, PatternDetector

__all__ = ["FocusPattern", "PatternDetector"]
