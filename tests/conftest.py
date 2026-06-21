"""
Test utilities and shared fixtures for wrench-voice.

WHY a conftest.py:
Pytest loads this file automatically before running tests in this directory.
It gives us shared fixtures (setup objects) that every test can request
by name — no duplication, no boilerplate.
"""

import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def sample_kb_dir() -> Path:
    """
    Provide a temporary directory with a few sample KB markdown files.
    Tests that need a knowledge base point here.
    """
    tmp = Path(tempfile.mkdtemp(prefix="wrench_test_"))
    (tmp / "toyota-22re.md").write_text("""
# Toyota 22RE

## Overview
2.4L inline-4, timing chain, fuel injected.

## Known Issues
- Timing chain rattle at 200k+ miles
- Cracked exhaust manifold

## Torque Specs
| Component | ft-lbs | Nm |
|-----------|--------|----|
| Head bolts | 58 | 78 |

## Fluid Capacities
| Fluid | Capacity |
|-------|----------|
| Oil | 4.5 qt |
""")
    (tmp / "ford-300-i6.md").write_text("""
# Ford 300 Inline-6

## Overview
4.9L inline-6, carbureted or EFI.

## Known Issues
- Plastic timing gear wear at 150k+
- Distributor shaft bushing wobble
""")
    return tmp


@pytest.fixture
def temp_cache_dir(monkeypatch) -> Path:
    """
    Redirect the parts-cache directory to a temp folder during tests.
    Prevents polluting the real ~/.cache/wrench-voice/.
    """
    tmp = Path(tempfile.mkdtemp(prefix="wrench_cache_"))
    # Monkeypatch the cache path constant so the module uses our temp dir
    monkeypatch.setenv("WRENCH_CACHE_DIR", str(tmp))
    return tmp
