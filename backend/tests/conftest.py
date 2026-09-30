"""Shared pytest configuration.

* Point the default database at a throwaway file so tests that build ``TestClient(app)``
  without a ``get_db`` override never migrate or touch ``backend/autoscape.db``.
* Disable the background startup model check so no test reaches vendor APIs.

Both must be set before ``app.database`` / ``app.main`` are imported, which is why this
lives in ``conftest.py`` rather than a fixture.
"""

import os
import tempfile
from pathlib import Path

_TEST_DB_DIR = Path(tempfile.mkdtemp(prefix="autoscape-tests-"))
os.environ.setdefault("DATABASE_URL", f"sqlite:///{(_TEST_DB_DIR / 'autoscape-test.db').as_posix()}")
os.environ["AUTOSCAPE_STARTUP_MODEL_CHECK"] = "0"
