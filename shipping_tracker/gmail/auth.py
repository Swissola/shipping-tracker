"""Gmail OAuth2 credential loading — two-path flow for laptop and headless Pi."""

from __future__ import annotations

import logging
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

SCOPES: list[str] = ["https://www.googleapis.com/auth/gmail.readonly"]


def load_credentials(
    token_path: str,
    credentials_path: str,
    scopes: list[str] = SCOPES,
) -> Credentials:
    """Load OAuth2 credentials from token_path, refreshing or re-authorizing as needed.

    Non-interactive (Pi) path: token.json exists and either:
      - creds.valid is True (not expired), OR
      - creds.expired and creds.refresh_token is set -> calls creds.refresh(Request())

    Interactive (laptop) path: token.json missing or refresh_token absent ->
      InstalledAppFlow.run_local_server() opens a browser, writes token.json.

    Args:
        token_path: Path to the token cache file (token.json). Must be git-ignored.
        credentials_path: Path to the OAuth client secrets file (credentials.json).
        scopes: OAuth scopes to request. Defaults to gmail.readonly (hard-coded).

    Returns:
        A valid Credentials object for use with the Gmail API.

    PRIVACY: token_path and credentials_path must be git-ignored.
    LOG SAFETY: Do not log the Credentials object or any field from it.
    """
    creds: Credentials | None = None

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, scopes)  # type: ignore[no-untyped-call]

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            # Non-interactive Pi path — no browser needed
            creds.refresh(Request())  # type: ignore[no-untyped-call]
        else:
            # Interactive laptop path — browser opens once
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, scopes)
            creds = flow.run_local_server(port=0)

        with open(token_path, "w") as fh:
            fh.write(creds.to_json())

    return creds
