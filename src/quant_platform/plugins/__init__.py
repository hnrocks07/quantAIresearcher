"""Plugin interfaces and registry for swappable components."""

from .broker import BrokerAdapter, FeeSchedule
from .research import ResearchSource
from .llm import LLMProvider
from .registry import PluginRegistry

__all__ = [
    "BrokerAdapter", "FeeSchedule",
    "ResearchSource",
    "LLMProvider",
    "PluginRegistry",
]
