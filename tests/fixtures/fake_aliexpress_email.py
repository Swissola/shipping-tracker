"""Synthetic AliExpress email body fixtures for parser tests.

PRIVACY: All values are synthetic. No real tracking numbers, email addresses,
sender domains, or order references. See CLAUDE.md privacy constraints.
Tracking numbers use FAKE prefix; sender uses @fakealixmail.example.com domain.
"""

# Fixture 1: label-anchored body — "Tracking number:" label (happy path, PARSE-02)
FAKE_ALIEXPRESS_SHIPPED_BODY = """\
Dear Customer,

Your order has been shipped.

Tracking number: FAKELP00FAKE00001
Carrier: FAKECARRIER

You can track your parcel at: https://faketrack.example.com

Thank you for shopping.
"""

# Fixture 2: "Logistics No." label variant
FAKE_ALIEXPRESS_LOGISTICS_BODY = """\
Hi,

Order dispatched.
Logistics No.: FAKEMM1234FAKE56CN
"""

# Fixture 3: "Tracking No." label variant
FAKE_ALIEXPRESS_TRACKING_NO_BODY = """\
Shipment notification

Tracking No. FAKEXX5678FAKE90CN
"""

# Fixture 4: pre-shipment — no tracking number (D-05 expected case)
FAKE_ALIEXPRESS_PRESHIPMENT_BODY = """\
Thank you for your order!

Your order is being processed. You will receive a shipping
notification once it has been dispatched.

Order reference: 500FAKE123456789
"""

# Fixture 5: shape-pattern fallback — no recognisable label, tracking number present
FAKE_ALIEXPRESS_NOLABEL_BODY = """\
Shipment update:
FAKEYT00000FAKE0001 is on its way to you.
"""

# Synthetic sender addresses (for can_parse tests) — no real domains
FAKE_ALIEXPRESS_SENDER = "shipping@fakemailaliexpress.example.com"
FAKE_OTHER_SENDER = "noreply@fakeotherstore.example.com"
