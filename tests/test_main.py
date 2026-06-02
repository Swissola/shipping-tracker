"""Unit tests for shipping_tracker.main path/dir handling.

Covers WR-02: main() must create a directory only when DATABASE_PATH actually
has a directory component, so the makedirs target matches where sqlite3.connect
writes. A bare filename or ":memory:" must never fabricate a spurious data/ dir.
All test data is synthetic — FAKE keys, no network (fetch is patched).
"""

from pathlib import Path
from unittest.mock import patch

import pytest


def test_bare_filename_db_path_creates_no_spurious_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WR-02: a bare-filename DATABASE_PATH writes the DB to the CWD and does
    NOT fabricate a data/ directory."""
    from shipping_tracker.main import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TRACKINGMORE_API_KEY", "FAKE_KEY")
    monkeypatch.setenv("DATABASE_PATH", "tracker.db")

    with patch(
        "shipping_tracker.main.fetch_unread_shipping_emails",
        return_value=[],
    ):
        result = main()

    assert result == 0
    # DB landed where connect() actually writes it (the CWD)...
    assert (tmp_path / "tracker.db").is_file()
    # ...and no mismatched data/ directory was fabricated.
    assert not (tmp_path / "data").exists()


def test_memory_db_path_creates_no_data_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """WR-02: DATABASE_PATH=:memory: must not create a data/ dir on disk."""
    from shipping_tracker.main import main

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TRACKINGMORE_API_KEY", "FAKE_KEY")
    monkeypatch.setenv("DATABASE_PATH", ":memory:")

    with patch(
        "shipping_tracker.main.fetch_unread_shipping_emails",
        return_value=[],
    ):
        result = main()

    assert result == 0
    assert not (tmp_path / "data").exists()
