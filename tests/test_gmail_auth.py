"""Unit tests for shipping_tracker.gmail.auth.

Covers GMAIL-01 (OAuth2 credential load) and GMAIL-03 (token persistence).
All test data is synthetic — no real tokens, client IDs, or email addresses.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from shipping_tracker.gmail.auth import load_credentials


def test_load_credentials_refreshes_expired_token(tmp_path: Path) -> None:
    """load_credentials calls creds.refresh() when token is expired with refresh_token.

    GMAIL-01/GMAIL-03: Non-interactive Pi path — refresh without browser.
    All token values are synthetic FAKE-prefixed data.
    """
    token_file = tmp_path / "token.json"
    token_file.write_text(
        json.dumps(
            {
                "token": "FAKEACCESSTOKEN",
                "refresh_token": "FAKEREFRESHTOKEN",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "FAKECLIENTID.apps.googleusercontent.com",
                "client_secret": "FAKECLIENTSECRET",
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            }
        )
    )

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "FAKEREFRESHTOKEN"
    mock_creds.to_json.return_value = '{"token": "REFRESHEDFAKETOKEN"}'

    with (
        patch(
            "shipping_tracker.gmail.auth.Credentials.from_authorized_user_file",
            return_value=mock_creds,
        ),
        patch("shipping_tracker.gmail.auth.Request"),
    ):
        result = load_credentials(str(token_file), "credentials.json")

    mock_creds.refresh.assert_called_once()
    # GMAIL-03: token.json must be written back after refresh
    assert token_file.exists()
    assert result is mock_creds


def test_load_credentials_writes_token_after_refresh(tmp_path: Path) -> None:
    """load_credentials writes updated token back to disk after refresh (GMAIL-03)."""
    token_file = tmp_path / "token.json"
    token_file.write_text(
        json.dumps(
            {
                "token": "FAKEACCESSTOKEN",
                "refresh_token": "FAKEREFRESHTOKEN",
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": "FAKECLIENTID.apps.googleusercontent.com",
                "client_secret": "FAKECLIENTSECRET",
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            }
        )
    )

    mock_creds = MagicMock()
    mock_creds.valid = False
    mock_creds.expired = True
    mock_creds.refresh_token = "FAKEREFRESHTOKEN"
    mock_creds.to_json.return_value = '{"token": "REFRESHEDFAKETOKEN"}'

    with (
        patch(
            "shipping_tracker.gmail.auth.Credentials.from_authorized_user_file",
            return_value=mock_creds,
        ),
        patch("shipping_tracker.gmail.auth.Request"),
    ):
        load_credentials(str(token_file), "credentials.json")

    mock_creds.to_json.assert_called_once()
    written = token_file.read_text()
    assert "REFRESHEDFAKETOKEN" in written


def test_load_credentials_laptop_path_when_no_token(tmp_path: Path) -> None:
    """load_credentials uses InstalledAppFlow when no token file exists (laptop path).

    GMAIL-01: Interactive first-run path — browser flow.
    """
    token_file = tmp_path / "token.json"
    # Do NOT create the token file — simulate first run

    mock_flow = MagicMock()
    mock_new_creds = MagicMock()
    mock_new_creds.to_json.return_value = '{"token": "NEWLAPTOPFAKETOKEN"}'
    mock_flow.run_local_server.return_value = mock_new_creds

    with (
        patch(
            "shipping_tracker.gmail.auth.InstalledAppFlow.from_client_secrets_file",
            return_value=mock_flow,
        ),
        patch("shipping_tracker.gmail.auth.Request"),
    ):
        result = load_credentials(str(token_file), "FAKECREDENTIALS.json")

    mock_flow.run_local_server.assert_called_once_with(port=0)
    mock_new_creds.refresh.assert_not_called()
    assert token_file.exists(), "token.json must be written after first-run flow"
    assert result is mock_new_creds
