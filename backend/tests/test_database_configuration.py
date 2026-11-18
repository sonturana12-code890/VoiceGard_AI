from pathlib import Path

from sqlalchemy.engine import make_url

from backend.database import PROJECT_ROOT, _resolve_database_url


def test_relative_sqlite_url_is_anchored_to_project_root():
    url = make_url(_resolve_database_url("sqlite:///./voiceguard.db"))

    assert url.database is not None
    assert Path(url.database) == (PROJECT_ROOT / "voiceguard.db").resolve()


def test_in_memory_sqlite_url_remains_in_memory():
    url = make_url(_resolve_database_url("sqlite:///:memory:"))

    assert url.database == ":memory:"
