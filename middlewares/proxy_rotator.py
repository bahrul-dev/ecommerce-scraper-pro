"""
proxy_rotator.py
------------------
Middleware rotasi proxy dengan health tracking sederhana. Dipakai untuk
mendistribusikan request lewat beberapa IP berbeda -- berguna kalau
target situs menerapkan rate-limit atau blocking berbasis IP.

PENTING (kejujuran teknis): middleware ini TIDAK melakukan bypass
terhadap sistem anti-bot canggih (Cloudflare, DataDome, PerimeterX, dsb).
Itu butuh browser fingerprint spoofing tingkat lanjut, solving CAPTCHA,
dan proxy residensial premium -- di luar cakupan proyek ini secara
sengaja (lihat docs/ARCHITECTURE.md bagian scope boundary). Yang
middleware ini lakukan hanya:
  1. Rotasi IP antar request (mengurangi kemungkinan rate-limit per-IP)
  2. Menandai proxy yang gagal terus-menerus sebagai "unhealthy" dan
     sementara tidak dipakai (cooldown), lalu dicoba lagi setelah jeda

Kalau tidak ada proxy dikonfigurasi (PROXY_LIST kosong), middleware ini
otomatis pass-through -- request jalan langsung tanpa proxy, tidak error.
Ini supaya proyek tetap bisa dijalankan tanpa proxy di lingkungan
development/demo, tapi siap dipakai production kalau proxy tersedia.
"""

import logging
import os
import random
import time
from collections import defaultdict

logger = logging.getLogger("proxy_rotator")


class ProxyRotatorMiddleware:
    # Berapa lama proxy yang gagal terus "diistirahatkan" sebelum dicoba lagi
    COOLDOWN_SECONDS = 60
    # Setelah berapa kali gagal berturut-turut, proxy dianggap unhealthy
    FAILURE_THRESHOLD = 3

    def __init__(self, proxy_list: list[str]):
        self.proxy_list = proxy_list
        self._failure_count: dict[str, int] = defaultdict(int)
        self._cooldown_until: dict[str, float] = defaultdict(float)

        if self.proxy_list:
            logger.info(f"[proxy_rotator] Aktif dengan {len(self.proxy_list)} proxy")
        else:
            logger.info(
                "[proxy_rotator] Tidak ada proxy dikonfigurasi -- "
                "request akan jalan langsung tanpa proxy."
            )

    @classmethod
    def from_crawler(cls, crawler):
        # Proxy list bisa datang dari Scrapy settings ATAU environment
        # variable (PROXY_LIST, dipisah koma) -- supaya gampang dikonfigurasi
        # tanpa perlu edit kode saat deploy.
        settings_list = crawler.settings.getlist("PROXY_LIST", [])
        env_list = os.environ.get("PROXY_LIST", "")
        env_proxies = [p.strip() for p in env_list.split(",") if p.strip()]

        combined = list(settings_list) + env_proxies
        return cls(proxy_list=combined)

    def _healthy_proxies(self) -> list[str]:
        now = time.time()
        return [p for p in self.proxy_list if self._cooldown_until[p] <= now]

    def process_request(self, request, spider):
        if not self.proxy_list:
            return None  # Tidak ada proxy dikonfigurasi -> jalan langsung

        healthy = self._healthy_proxies()
        if not healthy:
            logger.warning(
                "[proxy_rotator] Semua proxy sedang cooldown, request "
                "jalan tanpa proxy untuk sementara."
            )
            return None

        chosen = random.choice(healthy)
        request.meta["proxy"] = chosen
        request.meta["_proxy_used"] = chosen  # buat tracking di process_response
        return None

    def process_response(self, request, response, spider):
        proxy = request.meta.get("_proxy_used")
        if not proxy:
            return response

        if response.status in (403, 429, 503):
            self._record_failure(proxy)
        else:
            self._failure_count[proxy] = 0  # reset kalau sukses

        return response

    def process_exception(self, request, exception, spider):
        proxy = request.meta.get("_proxy_used")
        if proxy:
            self._record_failure(proxy)
        return None  # biarkan Scrapy retry middleware yang tangani retry

    def _record_failure(self, proxy: str):
        self._failure_count[proxy] += 1
        if self._failure_count[proxy] >= self.FAILURE_THRESHOLD:
            self._cooldown_until[proxy] = time.time() + self.COOLDOWN_SECONDS
            logger.warning(
                f"[proxy_rotator] Proxy {proxy} unhealthy "
                f"({self._failure_count[proxy]} error berturut-turut), "
                f"cooldown {self.COOLDOWN_SECONDS}s"
            )
