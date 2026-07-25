"""Strategy lineage — tracks evolution from parent to child strategies."""

from __future__ import annotations

import json
from typing import Any

from ..database import get_db
from ..models import StrategyORM


def record_lineage(child_name: str, parent_names: list[str], generation: int | None = None) -> None:
    """Set parent IDs, generation, and lineage path on a child strategy."""
    with get_db() as db:
        child = db.query(StrategyORM).filter(StrategyORM.name == child_name).first()
        if not child:
            return

        parent_ids = []
        max_parent_gen = -1
        lineage_parts = []

        for pname in parent_names:
            parent = db.query(StrategyORM).filter(StrategyORM.name == pname).first()
            if parent:
                parent_ids.append(parent.id)
                max_parent_gen = max(max_parent_gen, parent.generation or 0)
                lineage_parts.append(parent.lineage_path or pname)

        child.parent_strategy_ids = json.dumps(parent_ids)
        child.generation = (generation if generation is not None else max_parent_gen + 1)
        child.lineage_path = " + ".join(lineage_parts) + " -> " + child_name
        db.flush()


def get_lineage(strategy_id: int) -> dict[str, Any]:
    """Get full lineage tree for a strategy."""
    with get_db() as db:
        strategy = db.query(StrategyORM).filter(StrategyORM.id == strategy_id).first()
        if not strategy:
            return {"error": "not found"}

        result = {
            "id": strategy.id,
            "name": strategy.name,
            "generation": strategy.generation or 0,
            "lineage_path": strategy.lineage_path or strategy.name,
            "source": strategy.source,
            "status": strategy.status,
            "win_rate": strategy.win_rate,
            "parents": [],
            "children": [],
        }

        if strategy.parent_strategy_ids:
            try:
                parent_ids = json.loads(strategy.parent_strategy_ids)
                for pid in parent_ids:
                    p = db.query(StrategyORM).filter(StrategyORM.id == pid).first()
                    if p:
                        result["parents"].append({
                            "id": p.id, "name": p.name, "generation": p.generation or 0,
                            "win_rate": p.win_rate, "status": p.status,
                        })
            except (json.JSONDecodeError, TypeError):
                pass

        all_strategies = db.query(StrategyORM).filter(
            StrategyORM.parent_strategy_ids.isnot(None)
        ).all()
        for s in all_strategies:
            try:
                pids = json.loads(s.parent_strategy_ids)
                if strategy.id in pids:
                    result["children"].append({
                        "id": s.id, "name": s.name, "generation": s.generation or 0,
                        "win_rate": s.win_rate, "status": s.status,
                    })
            except (json.JSONDecodeError, TypeError):
                pass

        return result


def get_evolution_tree() -> list[dict]:
    """Get the full strategy evolution tree across all generations."""
    with get_db() as db:
        strategies = db.query(StrategyORM).order_by(
            StrategyORM.generation.asc(), StrategyORM.created_at.asc()
        ).all()

        tree = []
        for s in strategies:
            parent_ids = []
            try:
                if s.parent_strategy_ids:
                    parent_ids = json.loads(s.parent_strategy_ids)
            except (json.JSONDecodeError, TypeError):
                pass

            tree.append({
                "id": s.id, "name": s.name,
                "generation": s.generation or 0,
                "lineage_path": s.lineage_path or s.name,
                "parent_ids": parent_ids,
                "source": s.source, "status": s.status,
                "win_rate": s.win_rate, "sharpe": s.sharpe_ratio,
            })

        return tree
