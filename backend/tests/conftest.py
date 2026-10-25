"""
Pytest configuration and shared fixtures for Sovereign tests.
"""
import sys
import os
import pytest

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


@pytest.fixture
def anyio_backend():
    return "asyncio"
