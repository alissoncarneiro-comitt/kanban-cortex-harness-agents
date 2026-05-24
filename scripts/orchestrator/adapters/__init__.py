"""Pipeline phase adapters."""
from .base import PhaseAdapter
from .claude import ClaudeAdapter, strip_skill_frontmatter
from .cursor import CursorAdapter

__all__ = [
    "PhaseAdapter",
    "ClaudeAdapter",
    "CursorAdapter",
    "strip_skill_frontmatter",
]
