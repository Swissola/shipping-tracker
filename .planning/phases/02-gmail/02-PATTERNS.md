# Phase 2: Gmail - Pattern Map

**Mapped:** 2026-05-31
**Files analyzed:** 8 new files
**Analogs found:** 8 / 8

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `shipping_tracker/gmail/__init__.py` | subpackage init | — | `shipping_tracker/parsers/__init__.py` | exact |
| `shipping_tracker/gmail/auth.py` | utility | request-response | `shipping_tracker/logging_config.py` | role-match (standalone config/setup function, fully typed, no class) |
| `shipping_tracker/gmail/query.py` | utility | transform | `shipping_tracker/parsers/base.py` | role-match (pure typed function, docstring style) |
| `shipping_tracker/gmail/client.py` | service | request-response | `shipping_tracker/main.py` + `shipping_tracker/logging_config.py` | role-match (orchestrating function, structlog, dotenv) |
| `tests/test_gmail_auth.py` | test | request-response | `tests/test_smoke.py` | role-match (pytest, FAKE-prefixed data, privacy docstring) |
| `tests/test_gmail_query.py` | test | transform | `tests/test_smoke.py` | exact (pure-function test, no mocking needed) |
| `tests/test_gmail_client.py` | test | request-response | `tests/test_smoke.py` | role-match (pytest, FAKE data, MagicMock) |
| `tests/fixtures/fake_gmail_message.py` | test fixture | — | `tests/conftest.py` | role-match (synthetic fixture module, FAKE prefix, privacy docstring) |

---

## Pattern Assignments

### `shipping_tracker/gmail/__init__.py` (subpackage init)

**Analog:** `shipping_tracker/parsers/__init__.py` (line 1)

**Module docstring pattern** (line 1):
```python
"""Parser sub-package — pluggable email parser implementations."""
```

Apply the same single-line docstring style:
```python
"""Gmail sub-package — OAuth2 auth, query construction, and message fetch."""
```

**Public re-export pattern** — the RESEARCH §Recommended Project Structure specifies:
```python
# __init__.py should re-export the public surface that main.py will import
from shipping_tracker.gmail.client import GmailClient, fetch_unread_shipping_emails
from shipping_tracker.gmail.client import RawEmail

__all__ = ["GmailClient", "fetch_unread_shipping_emails", "RawEmail"]
```

---

### `shipping_tracker/gmail/auth.py` (utility, request-response)

**Analog:** `shipping_tracker/logging_config.py`

**Module docstring pattern** (line 1):
```python
"""Logging configuration — structlog + RotatingFileHandler, compact JSON, no stdout."""
```
Mirror this style — one-line module docstring, dash-separated description of responsibility.

**Imports pattern** (lines 1-8 of logging_config.py):
```python
import logging
import logging.handlers
import os

import structlog
```
For `auth.py`, follow the same block order: stdlib first, then third-party, no relative imports at top level:
```python
"""Gmail OAuth2 credential loading — two-path flow for laptop and headless Pi."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
```

**Standalone function pattern** (`configure_logging` at line 10-11 of logging_config.py):
```python
def configure_logging(
    log_path: str = "logs/shipping-tracker.log",
    log_level: int = logging.WARNING,
) -> None:
    """Configure structlog with a rotating file handler.
    ...
    """
```
Mirror the named-parameter-with-defaults, no-`*args`/`**kwargs`, explicit return type, multi-paragraph docstring with `Args:` / `Returns:` sections.

**Core two-path credential function** — copy from RESEARCH §Pattern 1 verbatim (lines 203-237 of RESEARCH.md). The key structural points:
- `creds: Credentials | None = None` initialization
- `os.path.exists(token_path)` guard before `from_authorized_user_file`
- Non-interactive path: `creds.expired and creds.refresh_token` → `creds.refresh(Request())`
- Interactive path: `InstalledAppFlow.from_client_secrets_file` → `flow.run_local_server(port=0)`
- Always write back: `with open(token_path, "w") as fh: fh.write(creds.to_json())`

**Privacy docstring annotation** — every function that touches credential data must include the LOG SAFETY notice (see RESEARCH §Pattern 1, lines 219-222):
```python
    """Load OAuth2 credentials from token_path, refreshing or re-authorizing as needed.
    ...
    PRIVACY: token_path and credentials_path must be git-ignored.
    LOG SAFETY: Do not log the Credentials object or any field from it.
    """
```

**No structlog in auth.py** — `logging_config.py` demonstrates that setup modules use `logging.getLogger(__name__)` at most. `auth.py` should log only a single INFO-level message with no credential fields (message_id only as a pattern):
```python
import logging
logger = logging.getLogger(__name__)
# logger.info("credentials.loaded")  -- no fields from Credentials object
```

---

### `shipping_tracker/gmail/query.py` (utility, transform)

**Analog:** `shipping_tracker/parsers/base.py` (pure typed module, no side effects)

**Module docstring pattern** (line 1 of base.py):
```python
"""BaseParser abstract interface — all email parsers inherit from this class."""
```
Mirror:
```python
"""Gmail query builder — constructs server-side Gmail search query strings."""
```

**Imports pattern** (lines 1-4 of base.py):
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
```
For `query.py`, there are no third-party imports — stdlib only:
```python
from __future__ import annotations
```

**Pure function with full typing pattern** — `base.py` shows every parameter and return fully typed under mypy --strict. Mirror with:
```python
def build_query(senders: list[str], window_days: int) -> str:
    """Build a Gmail search query string for unread shipping emails.

    Args:
        senders: Sender addresses or domains, e.g. ["@aliexpress.com"]
        window_days: How many days back to look (e.g. 30 -> newer_than:30d)

    Returns:
        Query string like: is:unread from:(sender1 OR sender2) newer_than:30d
    """
```

**No logging** in this module — it is a pure transform. `base.py` has no logging; maintain that pattern.

---

### `shipping_tracker/gmail/client.py` (service, request-response)

**Analog:** `shipping_tracker/main.py` (orchestrator function) + `shipping_tracker/logging_config.py` (structlog usage)

**Module docstring pattern** (line 1 of main.py):
```python
"""Pipeline orchestrator — stub for Phase 1."""
```
Mirror:
```python
"""Gmail client — service construction, message fetch loop, and RawEmail assembly."""
```

**Imports pattern** (lines 1-9 of main.py):
```python
import logging

from dotenv import load_dotenv

from shipping_tracker.logging_config import configure_logging
```
For `client.py`, add `TYPE_CHECKING` guard for `GmailResource` per RESEARCH §Pattern 6:
```python
from __future__ import annotations

import base64
import logging
import time
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from shipping_tracker.gmail.auth import load_credentials

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource
```

**Structlog logger creation** (main.py line 9):
```python
logger = logging.getLogger(__name__)
```
Identical pattern in client.py — `logger = logging.getLogger(__name__)`.

**Return type annotation on function** (main.py lines 12-13):
```python
def main() -> int:
    """Run the shipping-tracker pipeline.
```
Mirror for client functions with explicit return types and multi-line docstrings with `Args:` / `Returns:` / `Raises:` blocks.

**RawEmail dataclass** — mirror `TrackingInfo` in `parsers/base.py` (lines 7-11):
```python
@dataclass
class TrackingInfo:
    """Structured tracking data extracted from a shipping email."""

    tracking_number: str
    carrier: str
```
Mirror as:
```python
@dataclass(frozen=True)
class RawEmail:
    """A single matching email from Gmail, ready for parser dispatch.

    PRIVACY: Do not log sender or body fields directly. Log only message_id
    (a non-PII opaque identifier) for traceability.
    """

    message_id: str   # Gmail message ID — Phase 4 dedup key
    sender: str       # From: header value — used by BaseParser.can_parse()
    body: str         # Plain-text body — used by BaseParser.extract()
```
Note: use `frozen=True` (unlike `TrackingInfo` which omits it) — RESEARCH §Pattern 5. Also note `TrackingInfo` does NOT have a custom `__repr__`; `RawEmail` should suppress the default repr or add a safe one that omits `sender` and `body`:
```python
    def __repr__(self) -> str:
        return f"RawEmail(message_id={self.message_id!r})"
```

**LOG-02 discipline** — `main.py` line 25 shows the correct structlog call shape with no PII fields:
```python
logger.warning("shipping_tracker started — pipeline stub, no work performed")
```
In `client.py`, every log call must follow this pattern — keyword field is `message_id=` (opaque) or `count=N` only. Never `sender=`, `body=`, `subject=`.

**Core patterns** — see RESEARCH §Pattern 3 (paginated list, lines 279-307), §Pattern 4 (body extraction, lines 321-354), §Pattern 7 (HttpError backoff, lines 413-429). These are new patterns with no existing codebase analog; the planner/executor must copy them verbatim from RESEARCH.md and adapt for full typing.

---

### `tests/test_gmail_auth.py` (test, request-response)

**Analog:** `tests/test_smoke.py`

**Module docstring pattern** (line 1-6 of test_smoke.py):
```python
"""Smoke tests for the shipping-tracker package.

Verifies importability, entry point behavior, and pluggable parser scaffold.
All test data is synthetic — no real tracking numbers or personal data.
"""
```
Mirror — include the "all test data is synthetic" privacy line:
```python
"""Unit tests for shipping_tracker.gmail.auth.

Covers GMAIL-01 (OAuth2 credential load) and GMAIL-03 (token persistence).
All test data is synthetic — no real tokens, client IDs, or email addresses.
"""
```

**Import pattern** (lines 1-11 of test_smoke.py):
```python
import subprocess

import pytest

from shipping_tracker.parsers.base import BaseParser, TrackingInfo
```
For `test_gmail_auth.py`:
```python
import json
import os
from unittest.mock import MagicMock, patch

import pytest

from shipping_tracker.gmail.auth import load_credentials
```

**Test function docstring pattern** (test_smoke.py line 14-15):
```python
def test_package_importable() -> None:
    """The shipping_tracker package is importable without error."""
```
All test functions: one-line docstring, snake_case name, `-> None` return annotation.

**FAKE prefix on all test data** (test_smoke.py lines 35-36):
```python
ti = TrackingInfo(tracking_number="FAKE123", carrier="FAKECARRIER")
```
In auth tests, all token values use `FAKE` prefix: `"FAKEACCESSTOKEN"`, `"FAKEREFRESHTOKEN"`, `"FAKECLIENTID"`, `"FAKECLIENTSECRET"`.

**`tmp_path` fixture for file I/O** — test_smoke.py does not need it, but `conftest.py` demonstrates the pytest fixture pattern. In `test_gmail_auth.py`, use `pytest`'s built-in `tmp_path` fixture to write synthetic `token.json`:
```python
def test_load_credentials_refreshes_expired_token(tmp_path: pytest.TempPathFactory) -> None:
    token_file = tmp_path / "token.json"
    token_file.write_text(json.dumps({...FAKE values...}))
```
(See RESEARCH §Code Examples lines 617-641 for the complete pattern to copy.)

**`pytest.raises` pattern** (test_smoke.py line 30):
```python
with pytest.raises(TypeError):
    BaseParser()  # type: ignore[abstract]
```
Mirror for the "no token + no refresh_token on headless Pi → RuntimeError" path.

---

### `tests/test_gmail_query.py` (test, transform)

**Analog:** `tests/test_smoke.py` (pure assertion tests, no mocking)

**Module docstring pattern** — same as above, with "all test data is synthetic":
```python
"""Unit tests for shipping_tracker.gmail.query.

Covers GMAIL-02 query string construction for single/multiple senders and window sizes.
All test data is synthetic — no real sender addresses.
"""
```

**Pure assertion test pattern** (test_smoke.py lines 27-37 — no subprocess, no mocks):
```python
def test_base_parser_is_abstract() -> None:
    """BaseParser cannot be instantiated directly — it is abstract."""
    with pytest.raises(TypeError):
        BaseParser()  # type: ignore[abstract]


def test_tracking_info_dataclass() -> None:
    """TrackingInfo stores tracking_number and carrier as a dataclass."""
    ti = TrackingInfo(tracking_number="FAKE123", carrier="FAKECARRIER")
    assert ti.tracking_number == "FAKE123"
    assert ti.carrier == "FAKECARRIER"
```
Query tests require no mocking — pure string assertions. Mirror:
```python
def test_build_query_single_sender() -> None:
    """build_query produces correct q string for a single sender."""
    q = build_query(["@aliexpress.com"], 30)
    assert q == "is:unread from:(@aliexpress.com) newer_than:30d"
```
(See RESEARCH §Code Examples lines 591-606 for the full set of cases to copy.)

**FAKE-prefixed sender values** — use `"@fakestore.example.com"` not real domains.

---

### `tests/test_gmail_client.py` (test, request-response)

**Analog:** `tests/test_smoke.py` (structure, docstrings) — extended with `MagicMock` (no existing analog in codebase; copy from RESEARCH §Code Examples)

**Module docstring pattern** — same structure, extended:
```python
"""Unit tests for shipping_tracker.gmail.client.

Covers GMAIL-02 fetch loop, pagination, base64url decode, and LOG-02 PII safety.
All test data is synthetic — FAKE message IDs, FAKE sender addresses, FAKE bodies.
"""
```

**Import pattern** — combines test_smoke.py import style with mock:
```python
import logging
from unittest.mock import MagicMock, patch

import pytest

from shipping_tracker.gmail.client import fetch_unread_shipping_emails, RawEmail
from tests.fixtures.fake_gmail_message import FAKE_GMAIL_MESSAGE
```

**MagicMock chained-call pattern** — no existing codebase analog; copy from RESEARCH §Code Examples (lines 545-583). Key structure:
```python
mock_service = MagicMock()
mock_service.users().messages().list().execute.return_value = {
    "messages": [{"id": "FAKEMESSAGEID001", "threadId": "FAKETHREADID001"}],
}
mock_service.users().messages().get().execute.return_value = FAKE_GMAIL_MESSAGE

with patch("shipping_tracker.gmail.client.build_service", return_value=mock_service):
    results = fetch_unread_shipping_emails(
        senders=["@fakestore.example.com"],
        window_days=30,
    )
```

**LOG-02 PII-safety test pattern** — use `caplog` pytest fixture to assert no PII in log output. No existing analog in codebase; implement as:
```python
def test_fetch_does_not_log_sender_or_body(caplog: pytest.LogCaptureFixture) -> None:
    """fetch_unread_shipping_emails does not log sender addresses or body content (LOG-02)."""
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "FAKEMESSAGEID001"}],
    }
    mock_service.users().messages().get().execute.return_value = FAKE_GMAIL_MESSAGE

    with patch("shipping_tracker.gmail.client.build_service", return_value=mock_service):
        with caplog.at_level(logging.DEBUG, logger="shipping_tracker.gmail.client"):
            fetch_unread_shipping_emails(["@fakestore.example.com"], 30)

    log_text = caplog.text
    assert "@" not in log_text, "Log must not contain email addresses (LOG-02)"
    assert "FAKE1234567890" not in log_text, "Log must not contain body content (LOG-02)"
```

**All test data FAKE-prefixed** — no real message IDs, addresses, or tracking numbers anywhere in the file.

---

### `tests/fixtures/fake_gmail_message.py` (test fixture module)

**Analog:** `tests/conftest.py`

**Privacy module docstring pattern** (conftest.py lines 1-7):
```python
"""Shared pytest fixtures for shipping-tracker tests.

PRIVACY: All fixtures use synthetic data. No real tracking numbers,
email addresses, order IDs, or personal names may appear in this file
or in tests/fixtures/. See CLAUDE.md privacy constraints.
"""
```
Mirror — fixtures module must open with this privacy docstring:
```python
"""Synthetic Gmail API message fixtures for tests.

PRIVACY: All values are synthetic. No real message IDs, email addresses,
subjects, tracking numbers, or personal names. See CLAUDE.md privacy constraints.
"""
```

**Synthetic data naming pattern** (conftest.py lines 12-18):
```python
@pytest.fixture
def synthetic_email_body() -> str:
    """A synthetic AliExpress-style email body with fake tracking data."""
    return (
        "Your order has shipped!\n"
        "Tracking number: FAKE1234567890\n"
        "Carrier: FAKECARRIER\n"
    )
```
In the fixture module, FAKE prefix is required on all values: `"FAKEMESSAGEID001"`, `"FAKETHREADID001"`, `"shipping@fakestore.example.com"`. The full fixture dict is in RESEARCH §Code Examples (lines 514-533):
```python
FAKE_GMAIL_MESSAGE: dict[str, object] = {
    "id": "FAKEMESSAGEID001",
    "threadId": "FAKETHREADID001",
    "payload": {
        "mimeType": "multipart/alternative",
        "headers": [
            {"name": "From", "value": "shipping@fakestore.example.com"},
            {"name": "Subject", "value": "Your FAKE order has shipped"},
        ],
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {
                    # base64url of "Your order has shipped!\nTracking: FAKE1234567890\n"
                    "data": "WW91ciBvcmRlciBoYXMgc2hpcHBlZCEKVHJhY2tpbmc6IEZBS0UxMjM0NTY3ODkwCg"
                },
            }
        ],
    },
}
```
Note: tighten the type annotation from RESEARCH's `dict` to `dict[str, object]` for mypy --strict.

---

## Shared Patterns

### mypy --strict: `from __future__ import annotations`

**Source:** `shipping_tracker/parsers/base.py` and `shipping_tracker/logging_config.py` (neither currently use it, but `pyproject.toml` enforces `strict = true` and `python_version = "3.11"`)

**Apply to:** `auth.py`, `client.py`, `query.py` — all three modules use `X | Y` union syntax and `list[str]` generics. Under Python 3.11 with mypy strict, `from __future__ import annotations` is not strictly required for these constructs (they are available natively in 3.11), but it is good practice and consistent. The `TYPE_CHECKING` guard in `client.py` does require `from __future__ import annotations` if `GmailResource` is used as a bare annotation rather than a string literal.

**Implementation note:** RESEARCH §Pattern 6 shows the correct form:
```python
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from googleapiclient._apis.gmail.v1 import GmailResource
```

### mypy --strict: `[[tool.mypy.overrides]]` Block

**Source:** `pyproject.toml` lines 41-43:
```toml
[[tool.mypy.overrides]]
module = ["google.*", "googleapiclient.*"]
ignore_missing_imports = true
```
This block already exists. The planner must add `google-api-python-client-stubs>=1.37` to the `dev` optional-dependencies group (pyproject.toml line 21-25) so that `GmailResource` can be resolved by mypy via the stubs. No changes to the overrides block are needed.

### structlog PII-safe logging discipline

**Source:** `shipping_tracker/main.py` line 25:
```python
logger.warning("shipping_tracker started — pipeline stub, no work performed")
```
**Apply to:** `client.py`

Rule: only `message_id=` (opaque string) and `count=N` (integer) may appear as structured log fields. Never `sender=`, `body=`, `subject=`, or any field from the `RawEmail` dataclass except `message_id`. This is the LOG-02 constraint from CONTEXT.md §Established Patterns and RESEARCH §Anti-Patterns.

Concrete safe log calls:
```python
logger.info("gmail.fetch.complete", count=len(raw_emails))
logger.debug("gmail.message.fetched", message_id=msg_id)
# WRONG: logger.debug("gmail.message.fetched", sender=sender, body=body[:100])
```

### Privacy docstring annotation

**Source:** `tests/conftest.py` lines 1-7 (module level) and line 13 (fixture level)

**Apply to:** Every new test file and the fixture module.

Module-level pattern (adjust text to match the file's content):
```
PRIVACY: All fixtures use synthetic data. No real tracking numbers,
email addresses, order IDs, or personal names may appear in this file
or in tests/fixtures/. See CLAUDE.md privacy constraints.
```

Function/docstring-level pattern for any function that touches credential-adjacent data in source modules:
```
PRIVACY: token_path and credentials_path must be git-ignored.
LOG SAFETY: Do not log the Credentials object or any field from it.
```

### `.env`-driven configuration

**Source:** `shipping_tracker/main.py` lines 22-23:
```python
load_dotenv()
configure_logging()
```
`main.py` is the only place `load_dotenv()` is called. New `client.py` and `auth.py` read config values via `os.getenv()` — they do NOT call `load_dotenv()` themselves. The caller (`main.py`) ensures the env is populated before the Gmail layer is invoked.

New env vars (add to `.env.example`):
```bash
GMAIL_TOKEN_PATH=token.json
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_SENDER_LIST=@aliexpress.com
GMAIL_LOOKBACK_DAYS=30
```

### SCOPES constant — hard-coded, never configurable

**Source:** RESEARCH §D-03 and §Anti-Patterns ("never read scope from config")

**Apply to:** `auth.py`

```python
SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]
```
This constant must be defined at module level in `auth.py` and never read from `.env`. It is not a user-facing configuration value — it is a hard security boundary.

---

## No Analog Found

All 8 files have analogs drawn from the Phase 1 scaffold. However, several internal patterns within files have no existing codebase precedent and must be sourced directly from RESEARCH.md:

| Pattern | Source File | RESEARCH.md Reference |
|---------|-------------|----------------------|
| `MagicMock` chained Gmail service mock | `tests/test_gmail_client.py` | §Code Examples lines 545-583 |
| `caplog` PII-safety assertion | `tests/test_gmail_client.py` | §Anti-Patterns §Pitfall 4 |
| `nextPageToken` pagination loop | `client.py` | §Pattern 3 lines 279-307 |
| `_extract_body` MIME walk | `client.py` | §Pattern 4 lines 321-354 |
| `_decode_base64url` padding normalisation | `client.py` | §Pattern 4 lines 344-354 |
| `_execute_with_backoff` HttpError retry | `client.py` | §Pattern 7 lines 413-429 |
| `build_service` with `GmailResource` annotation | `client.py` | §Pattern 6 lines 386-400 |

---

## Metadata

**Analog search scope:** `shipping_tracker/`, `tests/`, `pyproject.toml`
**Files scanned:** 8 existing Phase 1 files
**Pattern extraction date:** 2026-05-31
