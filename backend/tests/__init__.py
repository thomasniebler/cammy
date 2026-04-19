"""Test infrastructure for cammy."""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


def get_test_data_dir() -> Path:
    """Get test data directory."""
    return Path(__file__).parent / "data"


def get_temp_dir() -> Path:
    """Get temporary directory for tests."""
    import tempfile

    return Path(tempfile.mkdtemp())
