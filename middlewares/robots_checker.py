"""
robots_checker.py
------------------
Middleware untuk memastikan setiap request scraping mematuhi robots.txt
target domain sebelum request dieksekusi. Ini adalah bagian dari prinsip
"ethical scraping" yang jadi salah satu requirement utama pekerjaan ini.

Cara kerja:
1. Ambil dan cache robots.txt per domain (supaya tidak fetch berulang-ulang).
2. Cek apakah path yang mau di-scrape diizinkan untuk user-agent kita.
3. Jika tidak diizinkan -> request di-drop, dicatat ke log, dan spider lanjut
   ke URL berikutnya (tidak crash, tidak retry paksa).

Digunakan sebagai downloader middleware di Scrapy settings.py:

    DOWNLOADER_MIDDLEWARES = {
        "middlewares.robots_checker.RobotsComplianceMiddleware": 100,
    }
"""

import logging
import urllib.robotparser
from urllib.parse import urlparse

from scrapy.exceptions import IgnoreRequest

logger = logging.getLogger("robots_checker")


class RobotsComplianceMiddleware:
    """Cek robots.txt sebelum setiap request diproses."""

    def __init__(self, user_agent: str):
        self.user_agent = user_agent
        self._parsers_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

    @classmethod
    def from_crawler(cls, crawler):
        user_agent = crawler.settings.get("USER_AGENT", "EcommerceScraperPro/1.0")
        return cls(user_agent=user_agent)

    def _get_parser(self, base_url: str) -> urllib.robotparser.RobotFileParser:
        """Ambil parser robots.txt dari cache, atau fetch & simpan jika belum ada."""
        if base_url not in self._parsers_cache:
            robots_url = f"{base_url}/robots.txt"
            parser = urllib.robotparser.RobotFileParser()
            parser.set_url(robots_url)
            try:
                parser.read()
                logger.info(f"[robots_checker] Loaded robots.txt from {robots_url}")
            except Exception as e:
                # Kalau robots.txt tidak bisa diakses, default: anggap semua diizinkan
                # tapi log sebagai warning supaya tetap traceable.
                logger.warning(
                    f"[robots_checker] Gagal fetch {robots_url}: {e}. "
                    "Melanjutkan dengan asumsi diizinkan."
                )
                parser = None
            self._parsers_cache[base_url] = parser
        return self._parsers_cache[base_url]

    def process_request(self, request, spider):
        parsed = urlparse(request.url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._get_parser(base_url)

        if parser is None:
            return None  # robots.txt tidak tersedia -> lanjut (fail-open dengan log)

        allowed = parser.can_fetch(self.user_agent, request.url)
        if not allowed:
            logger.warning(
                f"[robots_checker] BLOCKED oleh robots.txt: {request.url}"
            )
            raise IgnoreRequest(f"Disallowed by robots.txt: {request.url}")

        return None
