import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.bedrock import StubRunner  # noqa: E402
from app.ring_client import FixtureTransport, RingClient  # noqa: E402
from app.server import create_app  # noqa: E402
from app.store import IncidentStore  # noqa: E402

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


@pytest.fixture
def ring():
    return RingClient(FixtureTransport(FIXTURES_DIR))


@pytest.fixture
def store(tmp_path):
    db_path = tmp_path / "test.db"
    s = IncidentStore(str(db_path), evidence_dir=tmp_path / "evidence")
    yield s
    s.close()


@pytest.fixture
def bedrock():
    """A runner that never calls AWS. Empty, it raises BedrockUnavailable,
    which is the same path a dead shop wifi takes; a test that wants a
    proposal appends to ``replies`` first."""
    return StubRunner()


@pytest.fixture
def app(tmp_path, bedrock):
    db_path = tmp_path / "test.db"
    application = create_app(db_path=str(db_path), use_fixtures=True, bedrock=bedrock)
    application.config.update(TESTING=True)
    return application


@pytest.fixture
def client(app):
    return app.test_client()
