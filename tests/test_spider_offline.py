"""
test_spider_offline.py
------------------------
Versi spider yang sengaja meng-override start_urls dan allowed_domains
untuk crawling terhadap local fixture server (tests/fixtures/), BUKAN
situs asli. Tujuannya supaya seluruh pipeline (middleware, parsing,
cleaning) bisa diuji otomatis tanpa bergantung koneksi internet /
ketersediaan situs target -- praktik standar untuk test scraper yang
reliable dan reproducible di CI/CD.

Jalankan (dengan local fixture server sudah running di port 8899):
    scrapy runspider tests/test_spider_offline.py -o output/offline_test.json
"""

from scrapy_spider.spiders.ecommerce_spider import EcommerceSpider


class OfflineTestSpider(EcommerceSpider):
    name = "ecommerce_offline_test"
    allowed_domains = ["localhost", "127.0.0.1"]
    start_urls = ["http://localhost:8899/listing_page.html"]
