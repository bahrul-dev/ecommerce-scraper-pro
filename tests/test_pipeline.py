"""
test_pipeline.py
------------------
Test suite otomatis untuk proyek ini. Dibagi dua lapis:

1. Unit test murni untuk data_cleaning/cleaner.py -- cepat, tanpa
   dependency eksternal apapun.
2. Integration test untuk spider Scrapy -- menjalankan crawl penuh
   (spider + semua middleware ethical scraping) terhadap local HTTP
   server yang menyajikan HTML fixture (tests/fixtures/), yang isinya
   dibuat MENIRU struktur HTML asli books.toscrape.com. Sehingga
   TIDAK butuh koneksi internet maupun situs target yang harus selalu
   up. Ini best practice standar untuk testing web scraper yang
   reliable & reproducible di CI/CD pipeline manapun.

Jalankan:
    pytest tests/ -v
"""

import http.server
import json
import subprocess
import threading
import time
from pathlib import Path

import pytest

from data_cleaning.cleaner import (
    clean_product_record,
    parse_price,
    parse_rating,
    parse_star_rating_word,
    parse_availability,
    dedupe_repeated_text,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"
TEST_PORT = 8899


# ---------------------------------------------------------------------------
# Unit tests: data cleaning
# ---------------------------------------------------------------------------

class TestPriceParsing:
    def test_parses_simple_dollar_amount(self):
        assert parse_price("$24.99") == 24.99

    def test_parses_pound_amount(self):
        # Format asli books.toscrape.com pakai simbol pound
        assert parse_price("£51.77") == 51.77

    def test_parses_amount_with_thousand_separator(self):
        assert parse_price("$1,299.99") == 1299.99

    def test_returns_none_for_empty_input(self):
        assert parse_price(None) is None
        assert parse_price("") is None

    def test_returns_none_for_unparseable_text(self):
        assert parse_price("Contact us for price") is None


class TestRatingParsing:
    def test_parses_valid_numeric_rating(self):
        assert parse_rating("4") == 4.0

    def test_rejects_out_of_range_rating(self):
        assert parse_rating("9") is None
        assert parse_rating("-1") is None

    def test_handles_none(self):
        assert parse_rating(None) is None


class TestStarRatingWordParsing:
    """Test parsing rating dari format asli books.toscrape.com:
    class CSS berbentuk kata, mis. "star-rating Three"."""

    def test_parses_full_class_string(self):
        assert parse_star_rating_word("star-rating Three") == 3.0

    def test_parses_single_word(self):
        assert parse_star_rating_word("Five") == 5.0

    def test_parses_lowercase(self):
        assert parse_star_rating_word("star-rating one") == 1.0

    def test_returns_none_for_empty(self):
        assert parse_star_rating_word(None) is None
        assert parse_star_rating_word("") is None

    def test_returns_none_for_unrecognized_word(self):
        assert parse_star_rating_word("star-rating Unknown") is None


class TestAvailabilityParsing:
    def test_parses_in_stock_with_quantity(self):
        result = parse_availability("In stock (22 available)")
        assert result["in_stock"] is True
        assert result["quantity"] == 22

    def test_parses_out_of_stock(self):
        result = parse_availability("Out of stock")
        assert result["in_stock"] is False
        assert result["quantity"] == 0

    def test_handles_missing_input(self):
        result = parse_availability(None)
        assert result["in_stock"] is False
        assert result["quantity"] == 0


class TestDedupeRepeatedText:
    """Ditemukan lewat live-testing sungguhan: beberapa halaman produk di
    books.toscrape.com merender teks deskripsi dua kali berturut-turut
    dalam satu text node."""

    def test_detects_and_removes_duplication(self):
        original = "This is a sample description that repeats. "
        duplicated = original + original
        result = dedupe_repeated_text(duplicated)
        assert result.strip() == original.strip()

    def test_leaves_non_duplicated_text_unchanged(self):
        text = "This is a normal description with no duplication at all here."
        assert dedupe_repeated_text(text) == text

    def test_handles_short_text_safely(self):
        short_text = "Short."
        assert dedupe_repeated_text(short_text) == short_text

    def test_handles_none(self):
        assert dedupe_repeated_text(None) is None

    def test_real_world_duplicated_sample(self):
        """Sampel nyata dari live crawl (dipotong) yang memicu bug ini."""
        real_sample = (
            "It's hard to imagine a world without A Light in the Attic. "
            "This now-classic collection of poetry cel It's hard to imagine "
            "a world without A Light in the Attic. This now-classic "
            "collection of poetry celebrates its 20th anniversary."
        )
        result = dedupe_repeated_text(real_sample)
        assert result.count("It's hard to imagine a world") == 1


class TestCleanProductRecord:
    def test_valid_record_passes_cleaning(self):
        result = clean_product_record({
            "url": "https://books.toscrape.com/catalogue/p1.html",
            "name": "A Light in the Attic",
            "price_raw": "£51.77",
            "rating_raw": "star-rating Three",
            "availability_raw": "In stock (22 available)",
            "category": "Poetry",
            "description": "  Nice book  ",
            "scraped_at": "2026-07-10T00:00:00",
        })
        assert result.is_valid is True
        assert result.cleaned["price"] == 51.77
        assert result.cleaned["rating"] == 3.0
        assert result.cleaned["in_stock"] is True
        assert result.cleaned["stock_quantity"] == 22
        assert result.cleaned["description"] == "Nice book"

    def test_missing_name_marks_invalid(self):
        result = clean_product_record({
            "url": "https://example.com/p2",
            "name": "",
            "price_raw": "£10.00",
        })
        assert result.is_valid is False
        assert "Nama produk kosong" in result.errors

    def test_missing_price_marks_invalid(self):
        result = clean_product_record({
            "url": "https://example.com/p3",
            "name": "Some Product",
            "price_raw": None,
        })
        assert result.is_valid is False
        assert "Harga tidak bisa di-parse" in result.errors


# ---------------------------------------------------------------------------
# Integration test: full Scrapy crawl against local fixture server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def fixture_server():
    """Serve tests/fixtures/ over local HTTP untuk offline spider testing."""
    handler = lambda *args, **kwargs: http.server.SimpleHTTPRequestHandler(
        *args, directory=str(FIXTURES_DIR), **kwargs
    )
    server = http.server.HTTPServer(("localhost", TEST_PORT), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.5)  # beri waktu server siap menerima koneksi
    yield f"http://localhost:{TEST_PORT}"
    server.shutdown()


@pytest.fixture(scope="module")
def crawl_output(fixture_server, tmp_path_factory):
    """Jalankan spider offline test sebagai subprocess, kembalikan hasil JSON."""
    output_dir = tmp_path_factory.mktemp("crawl_output")
    output_file = output_dir / "result.json"

    result = subprocess.run(
        [
            "scrapy", "runspider", "tests/test_spider_offline.py",
            "-s", "ITEM_PIPELINES={}",
            "-s", "ROBOTSTXT_OBEY=False",
            # NOTE: sengaja TIDAK pakai suffix ":json" di sini.
            # Di Windows, path absolut sudah mengandung karakter ":" dari
            # drive letter (mis. "C:\Users\...\result.json"), sehingga
            # "-o path:json" akan salah di-parse oleh Scrapy (dianggap ada
            # dua separator ":"). Solusinya: cukup beri path dengan
            # ekstensi .json, Scrapy otomatis mendeteksi format dari
            # ekstensi file -- ini cara yang aman lintas OS.
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


class TestSpiderIntegration:
    def test_crawl_finds_all_products(self, crawl_output):
        assert len(crawl_output) == 3

    def test_each_product_has_required_fields(self, crawl_output):
        for product in crawl_output:
            assert product["name"], "Nama produk tidak boleh kosong"
            assert product["url"].startswith("http://localhost")
            assert product["price_raw"], "Harga mentah harus ada"
            assert product["rating_raw"], "Rating mentah harus ada"

    def test_product_names_match_fixtures(self, crawl_output):
        names = {p["name"] for p in crawl_output}
        assert "A Light in the Attic" in names
        assert "Tipping the Velvet" in names
        assert "Soumission" in names

    def test_cleaning_pipeline_accepts_all_scraped_items(self, crawl_output):
        """Pastikan semua item yang lolos scraping juga lolos data cleaning
        (mendeteksi regresi kalau ada perubahan selector yang merusak parsing)."""
        for raw_item in crawl_output:
            result = clean_product_record(raw_item)
            assert result.is_valid, f"Item gagal cleaning: {result.errors}"
