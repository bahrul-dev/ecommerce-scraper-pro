"""
user_agent_rotator.py
-----------------------
Rotasi User-Agent per request untuk menghindari fingerprinting sederhana
dan mendistribusikan beban identitas request. Daftar UA dibatasi ke
browser desktop mainstream (Chrome, Firefox, Safari, Edge) versi wajar --
tujuannya menyamarkan bahwa ini adalah traffic otomatis massal dari satu
UA yang sama, BUKAN untuk menyamar sebagai user tertentu atau melewati
proteksi keamanan (mis. WAF/anti-bot) secara curang.

Catatan etika: rotasi UA ini dipakai bersamaan dengan robots_checker dan
rate_limiter -- jadi tujuannya murni "berlaku wajar seperti browser
berbeda-beda", bukan menyembunyikan pelanggaran robots.txt.
"""

import random

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:126.0) "
    "Gecko/20100101 Firefox/126.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Edg/125.0.0.0",
]


class UserAgentRotatorMiddleware:
    """Downloader middleware: set header User-Agent secara acak per request."""

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def process_request(self, request, spider):
        request.headers["User-Agent"] = random.choice(USER_AGENTS)
        return None
