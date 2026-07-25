# AGENT_ARCHITECTURE.md
EngineeringManagerAgent -> PlannerAgent -> ResearchAgent (when needed) -> SeniorEngineerAgent -> ReviewerAgent -> remediation -> KnowledgeLearningAgent -> state/knowledge update -> next eligible phase.
All use Claude. Maximum two concurrent LLM agents. Persistent local state/knowledge mandatory.
