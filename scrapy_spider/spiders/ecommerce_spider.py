"""
ecommerce_spider.py
--------------------
Spider Scrapy single-process untuk mengambil data produk (buku) dari
books.toscrape.com. Logic parsing ada di base_ecommerce_parser.py
(dipakai bareng dengan versi distributed di ecommerce_distributed_spider.py).

Jalankan dengan:
    scrapy crawl ecommerce -O output/products.json

NOTE: gunakan -O (uppercase, overwrite) bukan -o (lowercase, append).
"""

import scrapy
from scrapy_spider.spiders.base_ecommerce_parser import EcommerceParserMixin


class EcommerceSpider(EcommerceParserMixin, scrapy.Spider):
    name = "ecommerce"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
    }
