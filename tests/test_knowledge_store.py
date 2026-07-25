"""Tests for knowledge store."""

from agent_system.config import Config
from agent_system.knowledge_store import KnowledgeStore
from agent_system.models import KnowledgeEntry


def test_store_and_retrieve(config: Config):
    ks = KnowledgeStore(config)
    entry = KnowledgeEntry(
        category="pattern",
        title="Test pattern",
        content="Pattern content",
        tags=["test", "P1"],
        phase_id="P1",
    )
    ks.store(entry)

    results = ks.retrieve(tags=["P1"])
    assert len(results) == 1
    assert results[0].title == "Test pattern"
    assert results[0].retrieval_count == 1


def test_retrieve_by_category(config: Config):
    ks = KnowledgeStore(config)
    ks.store(KnowledgeEntry(category="pattern", title="P1", tags=["a"]))
    ks.store(KnowledgeEntry(category="failure", title="F1", tags=["a"]))

    patterns = ks.retrieve(category="pattern")
    assert len(patterns) == 1
    assert patterns[0].category == "pattern"


def test_retrieve_for_phase(config: Config):
    ks = KnowledgeStore(config)
    ks.store(KnowledgeEntry(category="p", title="T1", tags=["0A"], phase_id="0A"))
    ks.store(KnowledgeEntry(category="p", title="T2", tags=["1"], phase_id="1"))

    results = ks.retrieve_for_phase("0A")
    assert len(results) == 1
    assert results[0].phase_id == "0A"


def test_count(config: Config):
    ks = KnowledgeStore(config)
    assert ks.count() == 0
    ks.store(KnowledgeEntry(category="p", title="T1"))
    assert ks.count() == 1


def test_skills_index_update(config: Config):
    ks = KnowledgeStore(config)
    ks.store(KnowledgeEntry(category="pattern", title="P1", phase_id="0A"))
    ks.update_skills_index([])

    skills_path = config.knowledge_dir / "SKILLS_INDEX.md"
    content = skills_path.read_text()
    assert "Pattern" in content
    assert "P1" in content


def test_persistence(config: Config):
    ks1 = KnowledgeStore(config)
    ks1.store(KnowledgeEntry(category="test", title="Persist", tags=["t"]))

    ks2 = KnowledgeStore(config)
    results = ks2.retrieve(tags=["t"])
    assert len(results) == 1
    assert results[0].title == "Persist"
