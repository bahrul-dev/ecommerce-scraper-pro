"""
test_api_spider_offline.py
-----------------------------
Override ApiProductSpider agar mengambil data dari local fixture JSON
server, bukan fakestoreapi.com sungguhan -- supaya test tidak bergantung
koneksi internet.

Jalankan (dengan local fixture server sudah running di port 8899):
    scrapy runspider tests/test_api_spider_offline.py -O output/api_offline_test.json
"""

from scrapy_spider.spiders.api_spider import ApiProductSpider


class OfflineApiTestSpider(ApiProductSpider):
    name = "api_products_offline_test"
    allowed_domains = ["localhost", "127.0.0.1"]
    start_urls = ["http://localhost:8899/api/products.json"]
