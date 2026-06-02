"""Unit tests for shipping_tracker.main path/dir and PII-safe logging.

Covers:
- WR-02: main() must create a directory only when DATABASE_PATH actually has a
  directory component, so the makedirs target matches where sqlite3.connect
  writes. A bare filename or ":memory:" must never fabricate a spurious data/ dir.
- WR-04: the missing-credentials branch must log only the basename of the
  credentials path, never a full path that could embed an OS username.
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


def test_missing_credentials_logs_basename_only_not_full_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """WR-04: a missing credentials file logged from an absolute path must not
    leak the directory / OS username — only the basename is logged."""
    from shipping_tracker import main as main_mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TRACKINGMORE_API_KEY", "FAKE_KEY")
    monkeypatch.setenv("DATABASE_PATH", ":memory:")
    # No-op logging setup so caplog captures cleanly and no log file is written.
    monkeypatch.setattr(main_mod, "configure_logging", lambda: None)

    leaky = FileNotFoundError()
    leaky.filename = "/home/SECRETUSER/.config/shipping-tracker/credentials.json"
    monkeypatch.setattr(
        main_mod,
        "fetch_unread_shipping_emails",
        lambda senders, window: (_ for _ in ()).throw(leaky),
    )

    with caplog.at_level("DEBUG"):
        assert main_mod.main() == 1

    missing = [
        r for r in caplog.records if "gmail.credentials.missing" in r.getMessage()
    ]
    assert missing, "expected a gmail.credentials.missing log record"
    for record in caplog.records:
        rendered = record.getMessage()
        assert "SECRETUSER" not in rendered
        assert "/home/" not in rendered
        assert ".config" not in rendered
    # The harmless basename IS allowed (and present) in the record.
    assert "credentials.json" in missing[0].getMessage()
