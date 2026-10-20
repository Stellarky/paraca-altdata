"""Polite HTTP client: fixed min interval, retries with backoff, timeouts,
optional on-disk cache, a per-run request cap, and request accounting."""
from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

from . import config

log = logging.getLogger(__name__)


class RequestBudgetExceeded(RuntimeError):
    pass


class PoliteClient:
    def __init__(self, min_interval: float = config.MIN_INTERVAL_SECONDS,
                 timeout: float = config.TIMEOUT_SECONDS, max_retries: int = config.MAX_RETRIES,
                 max_requests: int = config.MAX_REQUESTS_PER_RUN, cache_dir: Path | None = None,
                 session: requests.Session | None = None, sleep=time.sleep, clock=time.monotonic):
        self.min_interval, self.timeout, self.max_retries = min_interval, timeout, max_retries
        self.max_requests, self.cache_dir = max_requests, cache_dir
        self.s = session or requests.Session()
        self.s.headers.update({"User-Agent": config.USER_AGENT, "Accept-Language": "ja,en;q=0.8"})
        self._sleep, self._clock, self._last = sleep, clock, None
        self.requests_made = 0
        self.errors = 0
        self.bytes = 0

    def _wait(self):
        if self._last is not None:
            gap = self.min_interval - (self._clock() - self._last)
            if gap > 0:
                self._sleep(gap)

    def get(self, url: str, params: dict | None = None) -> str:
        full = url + ("?" + urlencode(params) if params else "")
        if self.cache_dir:
            p = self.cache_dir / (hashlib.sha1(full.encode()).hexdigest() + ".html")
            if p.exists():
                return p.read_text(encoding="utf-8")
        last_exc: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            if self.requests_made >= self.max_requests:
                raise RequestBudgetExceeded(f"request cap {self.max_requests} reached")
            self._wait()
            self.requests_made += 1
            try:
                r = self.s.get(url, params=params, timeout=self.timeout)
                self._last = self._clock()
                if r.status_code in (429, 503):
                    # Server asks us to back off: honour Retry-After, then retry.
                    wait = float(r.headers.get("Retry-After", 30 * attempt))
                    log.warning("HTTP %s for %s; backing off %.0fs", r.status_code, full, wait)
                    self._sleep(min(wait, 300))
                    last_exc = requests.HTTPError(f"HTTP {r.status_code}")
                    continue
                if r.status_code in (401, 403):
                    # Access refused: stop, never try to get around it.
                    raise PermissionError(f"HTTP {r.status_code} for {full}: access refused, stopping")
                r.raise_for_status()
                r.encoding = r.encoding or "utf-8"
                text = r.text
                self.bytes += len(r.content)
                if self.cache_dir:
                    self.cache_dir.mkdir(parents=True, exist_ok=True)
                    p.write_text(text, encoding="utf-8")
                return text
            except PermissionError:
                self.errors += 1
                raise
            except requests.RequestException as e:
                self._last = self._clock()
                self.errors += 1
                last_exc = e
                log.warning("attempt %d/%d failed for %s: %s", attempt, self.max_retries, full, e)
                self._sleep(min(5 * 2 ** (attempt - 1), 60))
        raise RuntimeError(f"giving up on {full}: {last_exc}")
