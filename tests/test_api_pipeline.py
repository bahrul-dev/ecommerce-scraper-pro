"""
test_api_pipeline.py
----------------------
Test untuk ApiProductSpider -- membuktikan pola scraping via API JSON
(bukan HTML parsing) juga berjalan benar dan bisa diuji offline dengan
cara yang sama seperti spider HTML biasa.
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


@pytest.fixture(scope="module")
def api_crawl_output(fixture_server, tmp_path_factory):
    output_dir = tmp_path_factory.mktemp("api_crawl_output")
    output_file = output_dir / "result.json"

    result = subprocess.run(
        [
            "scrapy", "runspider", "tests/test_api_spider_offline.py",
            "-s", "ITEM_PIPELINES={}",
            "-s", "ROBOTSTXT_OBEY=False",
            "-o", str(output_file),
            "-L", "ERROR",
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
        timeout=60,
    )

    assert result.returncode == 0, f"Scrapy crawl gagal: {result.stderr}"
    assert output_file.exists(), (
        f"File output tidak dibuat. stdout: {result.stdout}\nstderr: {result.stderr}"
    )

    with open(output_file) as f:
        return json.load(f)


class TestApiSpiderIntegration:
    def test_parses_all_products_from_json(self, api_crawl_output):
        assert len(api_crawl_output) == 3

    def test_no_html_selectors_involved(self, api_crawl_output):
        """Field wajib ada tanpa satu pun CSS/XPath selector dijalankan --
        membuktikan pola scraping ini murni JSON parsing."""
        for product in api_crawl_output:
            assert product["name"]
            assert product["price_raw"]
            assert product["source_type"] == "api"

    def test_maps_api_fields_correctly(self, api_crawl_output):
        names = {p["name"] for p in api_crawl_output}
        assert "Fjallraven Foldsack No. 1 Backpack" in names
        assert "Mens Cotton Jacket" in names

    def test_image_url_captured(self, api_crawl_output):
        for product in api_crawl_output:
            assert product["image_url"].startswith("https://")

    def test_cleaning_pipeline_accepts_api_sourced_items(self, api_crawl_output):
        from data_cleaning.cleaner import clean_product_record

        for raw_item in api_crawl_output:
            result = clean_product_record(raw_item)
            assert result.is_valid, f"Item API gagal cleaning: {result.errors}"
