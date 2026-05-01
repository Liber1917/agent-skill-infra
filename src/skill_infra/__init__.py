"""Agent Skill Infrastructure."""

from importlib.metadata import version as _version

try:
    __version__ = _version("agent-skill-infra")
except Exception:
    __version__ = "0.0.0"
