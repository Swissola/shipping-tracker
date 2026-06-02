"""Registrar Protocol and NullRegistrar placeholder.

PRIVACY (LOG-02): implementations MUST NOT embed tracking_number, carrier, or
any email content in exception messages. The dispatch loop logs only message_id
and type(exc).__name__ — a careless implementation that includes PII in its
exception string would defeat that guarantee.
"""

from __future__ import annotations

import json
import logging
import random
import time
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)


class QuotaExceededError(Exception):
    """Raised by TrackingMoreRegistrar on quota-exhausted (4021) or rate-limit (429).

    LOG-02: the message MUST NOT contain tracking_number, carrier, or the API key
    value — only structural strings such as "rate-limit" or "quota-exhausted".

    main()'s dispatch loop catches this specifically and breaks BEFORE the broad
    ``except Exception`` (D-06). register_and_persist propagates it unchanged.
    """


class Registrar(Protocol):
    """Callable protocol for registering a tracking number with an API."""

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        """Register a tracking number.

        Returns True on success (including TRACK-03 already-exists responses).
        Returns False or raises on any failure — caller will not persist rows.

        LOG-02: implementations MUST NOT embed tracking_number, carrier, or any
        email content in exception messages.
        """
        ...


class NullRegistrar:
    """Phase 4 placeholder — logs at debug, always returns False (deferred).

    Phase 5 replaces this with TrackingMoreRegistrar; zero changes to db.py
    or main.py are required.
    """

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        logger.debug("registrar.deferred")  # no tracking_number — LOG-02
        return False


_BASE_URL = "https://api.trackingmore.com"


class TrackingMoreRegistrar:
    """Implements the Registrar Protocol against the TrackingMore v4 API.

    D-04: accepts a constructor-injected ``httpx.Client`` so tests feed a mocked
    transport (zero live calls). In production, main() owns the client lifetime
    and closes it (Pitfall 4).

    LOG-02: never embed tracking_number, carrier, or the API key value in any log
    line or exception message — only structural strings.
    """

    def __init__(
        self,
        api_key: str,
        client: httpx.Client | None = None,
        *,
        retry_pause: float = 2.0,
        retry_jitter: float = 1.0,
        max_total_retries: int = 8,
    ) -> None:
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=10.0)  # D-03: 10s timeout
        self._retry_pause = retry_pause
        self._retry_jitter = retry_jitter
        # WR-05: this instance is created once and reused for every email in a
        # cron run, so the budget bounds TOTAL retries across the batch. Without
        # it, N transient failures would accumulate N x retry_pause of serial
        # sleep with no upper bound and could overrun the cron interval.
        self._retry_budget = max_total_retries

    def _sleep_for_retry(self) -> bool:
        """Consume one unit of the per-run retry budget and pause with jitter.

        Returns True if a retry may proceed (budget remained, slept); False if the
        per-run budget is exhausted and the caller should defer to the next cron
        run. The jitter (random.uniform(0, retry_jitter)) de-synchronises retries
        against a recovering API, matching the Gmail client's backoff. No PII is
        involved (LOG-02).
        """
        if self._retry_budget <= 0:
            return False
        self._retry_budget -= 1
        time.sleep(self._retry_pause + random.uniform(0, self._retry_jitter))
        return True

    def __call__(self, tracking_number: str, carrier: str | None) -> bool:
        # D-08: tracking_number always present; courier_code only when carrier is
        # truthy — omit the key entirely otherwise (never send null).
        payload: dict[str, str] = {"tracking_number": tracking_number}
        if carrier:
            payload["courier_code"] = carrier
        for attempt in range(2):
            try:
                resp = self._client.post(
                    f"{_BASE_URL}/v4/trackings/create",
                    json=payload,
                    headers={"Tracking-Api-Key": self._api_key},  # TRACK-02
                )
            except (httpx.TimeoutException, httpx.ConnectError):
                # D-02: one retry per call; WR-05: only if the per-run budget
                # remains, else defer to the next cron run.
                if attempt == 0 and self._sleep_for_retry():
                    continue
                return False  # second attempt / budget exhausted — defer
            try:
                return self._handle(resp)
            except httpx.HTTPStatusError:
                # 5xx transient (D-02): retry once, then defer. No PII in message.
                # WR-05: bounded by the per-run retry budget.
                if attempt == 0 and self._sleep_for_retry():
                    continue
                return False
        return False  # unreachable; mypy requires it

    def _handle(self, resp: httpx.Response) -> bool:
        if resp.status_code == 429:
            raise QuotaExceededError("rate-limit")  # D-06; no PII in message
        try:
            body = resp.json()
        except (json.JSONDecodeError, ValueError):
            # WR-06: tolerate ONLY a non-JSON body (Pitfall 6 / Q-2) — fall through
            # to the status checks. A non-decode error (e.g. an unexpected response
            # object) must NOT be masked as an empty body; let it propagate.
            body = {}
        meta_code = body.get("meta", {}).get("code")
        if meta_code in (200, 201):
            logger.info("registrar.created")  # D-07: INFO; no tracking_number
            return True
        if meta_code in (4016, 4101):  # 4101: defensive SDK-era code
            logger.info("registrar.already_exists")  # TRACK-03: duplicate = success
            return True
        if meta_code in (4021, 4190) or resp.status_code == 402:
            raise QuotaExceededError("quota-exhausted")  # D-01/D-06; no PII
        if resp.status_code >= 500:
            # Transient: __call__'s retry path handles it. No tracking_number in msg.
            raise httpx.HTTPStatusError(
                "server-error",
                request=resp.request,
                response=resp,
            )
        # Any other 4xx (incl. courier-required 4013/4015, Q-1 RESOLUTION): log the
        # structural meta_code only (no PII), do not persist — defers to next run.
        logger.error("registrar.error code=%s", meta_code)  # D-07: ERROR, no PII
        return False
