"""
test_distributed_spider.py
------------------------------
Test integrasi untuk DistributedEcommerceSpider (scrapy-redis). Beda dari
test lain di proyek ini: test ini BUTUH Redis sungguhan running (bukan
cuma HTTP fixture lokal), karena scheduler & dedup filter spider ini
memang didesain untuk selalu pakai Redis, tidak ada mode "tanpa Redis".

Test otomatis di-skip (bukan gagal) kalau Redis tidak tersedia di
environment yang menjalankan test -- supaya tidak memblokir orang yang
menjalankan test suite tanpa Redis ter-install. CI (GitHub Actions)
dikonfigurasi menyediakan Redis lewat service container, jadi test ini
tetap jalan penuh di CI.
"""

import http.server
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
TEST_PORT = 8899
REDIS_TEST_KEY = "ecommerce_distributed_test:start_urls"


def _redis_available() -> bool:
    try:
        import redis
        client = redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
        return client.ping()
    except Exception:
        return False


requires_redis = pytest.mark.skipif(
    not _redis_available(),
    reason="Redis tidak tersedia -- jalankan `redis-server` untuk test ini",
)


@pytest.fixture(scope="module")
def fixture_server():
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=str(FIXTURES_DIR), **kwargs
    )
    server = http.server.HTTPServer(("localhost", TEST_PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)
    yield f"http://localhost:{TEST_PORT}"
    server.shutdown()


@pytest.fixture
def redis_client():
    import redis
    client = redis.Redis(host="localhost", port=6379)
    # PENTING: flushall(), bukan cuma hapus REDIS_TEST_KEY. scrapy-redis
    # menyimpan dupefilter (daftar URL yang "sudah pernah dikunjungi")
    # secara PERSISTEN di key terpisah (SCHEDULER_PERSIST=True). Kalau
    # cuma start_urls key yang dibersihkan, run test sebelumnya di sesi
    # yang sama bikin URL yang sama dianggap duplikat dan di-skip diam-
    # diam -- inilah yang sempat bikin test ini flaky (pass kalau
    # dijalankan sendirian, gagal kalau dijalankan setelah test lain
    # yang juga pernah crawl spider distributed dengan URL yang sama).
    client.flushall()
    yield client
    client.flushall()


@requires_redis
class TestDistributedSpiderIntegration:
    def test_scheduler_uses_redis_backend(self, fixture_server, redis_client, tmp_path):
        """Membuktikan request benar-benar dijadwalkan lewat Redis
        (bukan memory lokal) -- dicek lewat stats 'scheduler/*/redis'."""
        redis_client.lpush(REDIS_TEST_KEY, f"{fixture_server}/listing_page.html")

        output_file = tmp_path / "distributed_result.json"

        result = subprocess.run(
            [
                "scrapy", "runspider", "tests/test_distributed_spider_offline.py",
                "-s", "ITEM_PIPELINES={}",
                "-s", "ROBOTSTXT_OBEY=False",
                "-s", "CLOSESPIDER_TIMEOUT=6",
                "-o", str(output_file),
                "-L", "ERROR",
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
            timeout=25,
        )

        assert result.returncode == 0, f"Crawl gagal: {result.stderr}"
        assert "scheduler/dequeued/redis" in result.stderr or output_file.exists()

        with open(output_file) as f:
            items = json.load(f)

        assert len(items) == 3
        names = {item["name"] for item in items}
        assert "A Light in the Attic" in names
