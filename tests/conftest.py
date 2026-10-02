"""
Global test configuration ensuring total test database isolation.
Guarantees that test runs NEVER connect to production databases.
"""

import os
import shutil
import tempfile
import pytest

# Enforce isolated test environment variables before ANY test file imports app
_test_dir = tempfile.mkdtemp(prefix="louders_test_isolation_")
_test_db_path = os.path.join(_test_dir, "test_isolated.db").replace("\\", "/")

# Pre-populate test db from production seed file so schema and test data are available
_repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_seed_db = os.path.join(_repo_root, "licenses.db")
if os.path.isfile(_seed_db):
    shutil.copy2(_seed_db, _test_db_path)

# Override environment variables strictly for test isolation
os.environ["APP_ENV"] = "development"
os.environ["DATABASE_URL"] = f"sqlite:///{_test_db_path}"
os.environ["ADMIN_USERNAME"] = "hanzoo"
os.environ["ADMIN_PASSWORD"] = "Hanzoo@2511"
os.environ.pop("RENDER", None)
os.environ.pop("PRODUCTION", None)


@pytest.fixture(scope="session", autouse=True)
def cleanup_isolated_test_suite():
    """Ensure temporary test sandbox is cleaned up after session."""
    yield
    try:
        shutil.rmtree(_test_dir, ignore_errors=True)
    except Exception:
        pass
