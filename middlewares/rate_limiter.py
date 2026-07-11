"""
rate_limiter.py
----------------
Middleware rate limiting adaptif. Selain AUTOTHROTTLE bawaan Scrapy,
middleware ini menambahkan:
  1. Minimum delay per-domain yang bisa dikonfigurasi terpisah dari delay global.
  2. Circuit breaker sederhana: kalau beberapa response berturut-turut kena
     429 (Too Many Requests) atau 503, delay dinaikkan otomatis (exponential backoff)
     sampai server "tenang" lagi.

Tujuan: menunjukkan praktik scraping yang bertanggung jawab -- tidak
membebani server target, dan otomatis mundur kalau server menunjukkan tanda
overload.
"""

import logging
import time
from collections import defaultdict

logger = logging.getLogger("rate_limiter")


class AdaptiveRateLimiterMiddleware:
    BASE_DELAY = 1.0          # detik, delay minimum antar request per domain
    MAX_DELAY = 30.0          # detik, batas atas backoff
    BACKOFF_MULTIPLIER = 2.0
    TRIGGER_STATUS_CODES = {429, 503}

    def __init__(self):
        self._last_request_time: dict[str, float] = {}
        self._current_delay: dict[str, float] = defaultdict(lambda: self.BASE_DELAY)
        self._consecutive_errors: dict[str, int] = defaultdict(int)

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        domain = request.url.split("/")[2]
        delay = self._current_delay[domain]
        last_time = self._last_request_time.get(domain, 0)
        elapsed = time.time() - last_time

        if elapsed < delay:
            sleep_time = delay - elapsed
            logger.debug(f"[rate_limiter] Sleeping {sleep_time:.2f}s for {domain}")
            time.sleep(sleep_time)

        self._last_request_time[domain] = time.time()
        return None

    def process_response(self, request, response, spider):
        domain = request.url.split("/")[2]

        if response.status in self.TRIGGER_STATUS_CODES:
            self._consecutive_errors[domain] += 1
            new_delay = min(
                self._current_delay[domain] * self.BACKOFF_MULTIPLIER,
                self.MAX_DELAY,
            )
            self._current_delay[domain] = new_delay
            logger.warning(
                f"[rate_limiter] Status {response.status} dari {domain}. "
                f"Backoff delay naik ke {new_delay:.2f}s "
                f"(error ke-{self._consecutive_errors[domain]})"
            )
        else:
            # Reset gradual kalau response sehat lagi
            if self._consecutive_errors[domain] > 0:
                self._consecutive_errors[domain] = 0
                self._current_delay[domain] = self.BASE_DELAY
                logger.info(f"[rate_limiter] {domain} pulih, delay direset ke base.")

        return response
