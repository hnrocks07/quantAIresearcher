"""Knowledge store for capturing and retrieving lessons, skills, patterns."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .config import Config
from .models import KnowledgeEntry, _now

logger = logging.getLogger(__name__)


class KnowledgeStore:

    def __init__(self, config: Config) -> None:
        self.config = config
        self._dir = config.knowledge_dir
        self._dir.mkdir(parents=True, exist_ok=True)
        self._index_path = self._dir / "knowledge_index.json"
        self._skills_path = self._dir / "SKILLS_INDEX.md"

    def _load_index(self) -> dict[str, Any]:
        if self._index_path.exists():
            with open(self._index_path) as f:
                return json.load(f)
        return {"entries": {}}

    def _save_index(self, data: dict[str, Any]) -> None:
        with open(self._index_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def store(self, entry: KnowledgeEntry) -> None:
        index = self._load_index()
        index["entries"][entry.entry_id] = entry.to_dict()
        self._save_index(index)

        entry_path = self._dir / f"{entry.entry_id}.json"
        with open(entry_path, "w") as f:
            json.dump(entry.to_dict(), f, indent=2, default=str)

        logger.info("Stored knowledge entry: %s [%s]",
                     entry.title, entry.category)

    def retrieve(self, tags: list[str] | None = None,
                  category: str = "") -> list[KnowledgeEntry]:
        index = self._load_index()
        results = []
        for data in index.get("entries", {}).values():
            entry = KnowledgeEntry.from_dict(data)
            if category and entry.category != category:
                continue
            if tags:
                if not any(t in entry.tags for t in tags):
                    continue
            entry.retrieval_count += 1
            entry.last_retrieved = _now()
            index["entries"][entry.entry_id] = entry.to_dict()
            results.append(entry)
        if results:
            self._save_index(index)
        return results

    def retrieve_for_phase(self, phase_id: str) -> list[KnowledgeEntry]:
        return self.retrieve(tags=[phase_id])

    def get_all(self) -> list[KnowledgeEntry]:
        index = self._load_index()
        return [KnowledgeEntry.from_dict(d)
                for d in index.get("entries", {}).values()]

    def update_skills_index(self, entries: list[KnowledgeEntry]) -> None:
        lines = ["# SKILLS_INDEX.md\n",
                  "Populated by KnowledgeLearningAgent.\n"]
        by_category: dict[str, list[KnowledgeEntry]] = {}
        for entry in self.get_all():
            cat = entry.category or "uncategorized"
            by_category.setdefault(cat, []).append(entry)

        for cat, items in sorted(by_category.items()):
            lines.append(f"\n## {cat.replace('_', ' ').title()}\n")
            for item in items:
                lines.append(f"- {item.title} (phase: {item.phase_id}, "
                              f"retrieved: {item.retrieval_count}x)")

        with open(self._skills_path, "w") as f:
            f.write("\n".join(lines) + "\n")

    def count(self) -> int:
        index = self._load_index()
        return len(index.get("entries", {}))
