"""Pytest configuration for KnowScraper test suite."""

import pytest


def pytest_collection_modifyitems(config, items):
    """Mark integration tests so they can be skipped with -m 'not integration'."""
    for item in items:
        if "integration" in item.fspath.basename:
            item.add_marker(pytest.mark.integration)
