"""Unit tests for shipping_tracker.gmail.client.

Covers GMAIL-02 fetch loop, pagination, base64url decode, and LOG-02 PII safety.
All test data is synthetic — FAKE message IDs, FAKE sender addresses, FAKE bodies.
"""

import logging
from unittest.mock import MagicMock, patch

import pytest

from shipping_tracker.gmail.client import (
    _decode_base64url,
    fetch_unread_shipping_emails,
)
from tests.fixtures.fake_gmail_message import FAKE_GMAIL_MESSAGE

# Synthetic second message fixture for pagination tests.
# PRIVACY: All values are synthetic — no real message IDs or email addresses.
FAKE_GMAIL_MESSAGE_2: dict[str, object] = {
    "id": "FAKEMESSAGEID002",
    "threadId": "FAKETHREADID002",
    "payload": {
        "mimeType": "multipart/alternative",
        "headers": [
            {"name": "From", "value": "dispatch@fakeshop.example.com"},
            {"name": "Subject", "value": "Your FAKE order FAKE002 has shipped"},
        ],
        "parts": [
            {
                "mimeType": "text/plain",
                "body": {
                    # base64url of "Your order has shipped!\nTracking: FAKE9876543210\n"
                    "data": (
                        "WW91ciBvcmRlciBoYXMgc2hpcHBlZCEKVHJhY2tpbmc6"
                        "IEZBS0U5ODc2NTQzMjEwCg"
                    ),
                },
            }
        ],
    },
}

# Shared fake credentials mock (no real tokens anywhere)
_FAKE_CREDS = MagicMock(name="FAKECREDENTIALS")


def test_fetch_returns_raw_emails() -> None:
    """fetch_unread_shipping_emails wraps matching messages as RawEmail objects."""
    mock_service = MagicMock()

    # messages().list().execute() returns one page with one message ID
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "FAKEMESSAGEID001", "threadId": "FAKETHREADID001"}],
        # no nextPageToken -> single page
    }

    # messages().get().execute() returns the full synthetic message
    mock_service.users().messages().get().execute.return_value = FAKE_GMAIL_MESSAGE

    with (
        patch(
            "shipping_tracker.gmail.client.load_credentials",
            return_value=_FAKE_CREDS,
        ),
        patch(
            "shipping_tracker.gmail.client.build_service",
            return_value=mock_service,
        ),
    ):
        results = fetch_unread_shipping_emails(
            senders=["@fakestore.example.com"],
            window_days=30,
        )

    assert len(results) == 1
    assert results[0].message_id == "FAKEMESSAGEID001"
    assert results[0].sender == "shipping@fakestore.example.com"
    assert "FAKE1234567890" in results[0].body


def test_fetch_pagination() -> None:
    """fetch_unread_shipping_emails follows nextPageToken across two pages."""
    mock_service = MagicMock()

    # First list call returns a nextPageToken + one ID;
    # second list call returns a second ID with no token.
    mock_service.users().messages().list().execute.side_effect = [
        {
            "messages": [{"id": "FAKEMESSAGEID001", "threadId": "FAKETHREADID001"}],
            "nextPageToken": "FAKEPAGETOKEN",
        },
        {
            "messages": [{"id": "FAKEMESSAGEID002", "threadId": "FAKETHREADID002"}],
        },
    ]

    # get() alternates between the two synthetic messages
    mock_service.users().messages().get().execute.side_effect = [
        FAKE_GMAIL_MESSAGE,
        FAKE_GMAIL_MESSAGE_2,
    ]

    with (
        patch(
            "shipping_tracker.gmail.client.load_credentials",
            return_value=_FAKE_CREDS,
        ),
        patch(
            "shipping_tracker.gmail.client.build_service",
            return_value=mock_service,
        ),
    ):
        results = fetch_unread_shipping_emails(
            senders=["@fakestore.example.com"],
            window_days=30,
        )

    assert len(results) == 2
    assert results[0].message_id == "FAKEMESSAGEID001"
    assert results[1].message_id == "FAKEMESSAGEID002"


def test_fetch_empty() -> None:
    """fetch_unread_shipping_emails returns [] when no messages match."""
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {}

    with (
        patch(
            "shipping_tracker.gmail.client.load_credentials",
            return_value=_FAKE_CREDS,
        ),
        patch(
            "shipping_tracker.gmail.client.build_service",
            return_value=mock_service,
        ),
    ):
        results = fetch_unread_shipping_emails(
            senders=["@fakestore.example.com"],
            window_days=30,
        )

    assert results == []


def test_decode_base64url_padding() -> None:
    """_decode_base64url decodes an unpadded base64url string without raising."""
    data = "WW91ciBvcmRlciBoYXMgc2hpcHBlZCEKVHJhY2tpbmc6IEZBS0UxMjM0NTY3ODkwCg"
    result = _decode_base64url(data)
    assert "FAKE1234567890" in result


def test_fetch_does_not_log_pii(caplog: pytest.LogCaptureFixture) -> None:
    """fetch_unread_shipping_emails does not log sender or body content (LOG-02)."""
    mock_service = MagicMock()
    mock_service.users().messages().list().execute.return_value = {
        "messages": [{"id": "FAKEMESSAGEID001"}],
    }
    mock_service.users().messages().get().execute.return_value = FAKE_GMAIL_MESSAGE

    with (
        patch(
            "shipping_tracker.gmail.client.load_credentials",
            return_value=_FAKE_CREDS,
        ),
        patch(
            "shipping_tracker.gmail.client.build_service",
            return_value=mock_service,
        ),
        caplog.at_level(logging.DEBUG, logger="shipping_tracker.gmail.client"),
    ):
        fetch_unread_shipping_emails(["@fakestore.example.com"], 30)

    assert "@" not in caplog.text, "Log must not contain email addresses (LOG-02)"
    assert "FAKE1234567890" not in caplog.text, (
        "Log must not contain body content (LOG-02)"
    )
