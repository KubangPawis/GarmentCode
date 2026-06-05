"""Root conftest: ensure the project root is first on sys.path so that
`mpfb_ingest` resolves to the top-level package, not the test sub-directory.

The tests/mpfb_ingest/ directory has an __init__.py (from Task 1) which causes
Python to shadow the real mpfb_ingest package when pytest adds tests/ to sys.path.
The pytest_configure hook runs before any test module is imported, so it can
establish the correct sys.path order and pre-import the real package.
"""
import sys
import importlib
from pathlib import Path


def pytest_configure(config):
    """Prepend project root to sys.path before any test collection."""
    root = str(Path(__file__).parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    # Pre-import the real mpfb_ingest so it wins the sys.modules race.
    real_pkg = Path(root) / "mpfb_ingest" / "__init__.py"
    if "mpfb_ingest" not in sys.modules:
        importlib.import_module("mpfb_ingest")
    elif str(sys.modules["mpfb_ingest"].__file__) != str(real_pkg):
        # Wrong package already loaded — evict and reload the real one.
        for key in list(sys.modules):
            if key == "mpfb_ingest" or key.startswith("mpfb_ingest."):
                del sys.modules[key]
        importlib.import_module("mpfb_ingest")
