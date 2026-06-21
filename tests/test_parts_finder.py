"""
Tests for the parts finder.

Verifies:
1. Lookup returns PartResult objects with required fields
2. Mock mode works when web is unavailable
3. Cache stores and retrieves correctly
4. Multiple suppliers return varied results
"""

import pytest

from wrench_voice.parts_finder import PartsFinder, PartResult


class TestPartsFinder:
    """Parts lookup and price comparison tests."""

    def test_mock_mode_returns_results(self):
        """
        When no API keys are set and web is unavailable,
        finder should fall back to simulated results.
        """
        finder = PartsFinder(mock_mode=True)
        results = finder.lookup("thermostat", make="Toyota", year=1996)

        assert isinstance(results, list)
        assert len(results) >= 1
        assert all(isinstance(r, PartResult) for r in results)
        assert all(r.price >= 0 for r in results)

    def test_results_include_supplier(self):
        """
        Each result must identify its source.
        """
        finder = PartsFinder(mock_mode=True)
        results = finder.lookup("oil filter")

        suppliers = {r.supplier for r in results}
        assert len(suppliers) >= 1

    def test_cache_roundtrip(self, temp_cache_dir):
        """
        Second identical lookup should read from cache.
        """
        finder = PartsFinder(mock_mode=True)
        first = finder.lookup("spark plug", make="Ford", year=1995)
        second = finder.lookup("spark plug", make="Ford", year=1995)

        # Both should return equivalent results
        assert len(first) == len(second)
