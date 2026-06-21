"""
Tests for the knowledge base.

Verifies:
1. KB loads markdown files from directory
2. Search returns ranked results
3. Empty query returns empty results
4. Relevant keywords score higher
"""

import pytest

from wrench_voice.kb import KnowledgeBase


class TestKnowledgeBase:
    """KB search and indexing tests."""

    def test_search_finds_relevant_docs(self, sample_kb_dir):
        """
        Searching "torque" should return documents with torque tables.
        """
        kb = KnowledgeBase(kb_dir=sample_kb_dir)
        results = kb.search("torque")

        assert len(results) >= 1
        assert any("torque" in r.title.lower() or "torque" in r.snippet.lower() for r in results)

    def test_empty_query_returns_nothing(self, sample_kb_dir):
        """
        Guard against useless search results from empty strings.
        """
        kb = KnowledgeBase(kb_dir=sample_kb_dir)
        results = kb.search("")
        assert len(results) == 0

    def test_unknown_term_returns_low_score(self, sample_kb_dir):
        """
        "turbocharger" shouldn't appear in our basic sample KB.
        """
        kb = KnowledgeBase(kb_dir=sample_kb_dir)
        results = kb.search("turbocharger")

        # Either empty or very low score
        if results:
            assert results[0].score < 0.2
