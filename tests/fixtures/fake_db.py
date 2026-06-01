"""Synthetic database fixtures for Phase 4 deduplication tests.

PRIVACY: All values are synthetic. No real tracking numbers, Gmail message IDs,
email addresses, or order references. See CLAUDE.md privacy constraints.
Message IDs use FAKEMSGID prefix; tracking numbers use FAKETRACK prefix.
"""

# Message IDs — opaque Gmail message IDs (non-PII, FAKE-prefixed for test safety)
FAKE_MESSAGE_ID_1 = "FAKEMSGID001"
FAKE_MESSAGE_ID_2 = "FAKEMSGID002"
FAKE_MESSAGE_ID_DUP = "FAKEMSGID003"  # a duplicate-notification email

# Tracking numbers — FAKE-prefixed, no real carrier format
FAKE_TRACKING_NUMBER_1 = "FAKETRACK001CN"
FAKE_TRACKING_NUMBER_2 = "FAKETRACK002CN"
