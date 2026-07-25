"""Agent definitions for the engineering team."""

from .base import BaseAgent
from .engineering_manager import EngineeringManagerAgent
from .planner import PlannerAgent
from .researcher import ResearchAgent
from .senior_engineer import SeniorEngineerAgent
from .reviewer import ReviewerAgent
from .knowledge_learning import KnowledgeLearningAgent

AGENT_REGISTRY: dict[str, type[BaseAgent]] = {
    "EngineeringManagerAgent": EngineeringManagerAgent,
    "PlannerAgent": PlannerAgent,
    "ResearchAgent": ResearchAgent,
    "SeniorEngineerAgent": SeniorEngineerAgent,
    "ReviewerAgent": ReviewerAgent,
    "KnowledgeLearningAgent": KnowledgeLearningAgent,
}

__all__ = [
    "BaseAgent",
    "EngineeringManagerAgent",
    "PlannerAgent",
    "ResearchAgent",
    "SeniorEngineerAgent",
    "ReviewerAgent",
    "KnowledgeLearningAgent",
    "AGENT_REGISTRY",
]
