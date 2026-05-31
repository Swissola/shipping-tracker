"""Synthetic Gmail API message fixtures for tests.

PRIVACY: All values are synthetic. No real message IDs, email addresses,
subjects, tracking numbers, or personal names. See CLAUDE.md privacy constraints.
"""

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
                    "data": (
                        "WW91ciBvcmRlciBoYXMgc2hpcHBlZCEKVHJhY2tpbmc6"
                        "IEZBS0UxMjM0NTY3ODkwCg"
                    ),
                },
            }
        ],
    },
}
