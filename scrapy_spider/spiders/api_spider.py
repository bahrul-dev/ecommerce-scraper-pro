"""
api_spider.py
--------------
Spider yang mendemonstrasikan pola scraping BERBEDA dari HTML parsing:
mengambil data langsung dari API JSON tersembunyi/publik situs target,
alih-alih parsing struktur HTML.

Ini praktik yang sangat umum dipakai scraper profesional: sebelum
menulis satu baris CSS selector pun, langkah pertama adalah membuka
DevTools browser (tab Network > filter XHR/Fetch) untuk cek apakah
situs target memuat datanya lewat panggilan API internal. Kalau ada,
scraping lewat API jauh lebih:
  - Stabil (gak rusak kalau situs redesign HTML/CSS-nya)
  - Cepat (gak perlu render/parsing HTML penuh)
  - Ringan (payload JSON jauh lebih kecil dari HTML+CSS+JS)

Target di sini: fakestoreapi.com -- REST API publik yang memang
disediakan untuk keperluan testing/prototyping (bukan API internal situs
e-commerce sungguhan), supaya demo ini tetap 100% legal dipakai siapa
saja tanpa reverse-engineering situs privat.

CATATAN UNTUK KASUS NYATA: kalau target aslinya adalah API internal
situs e-commerce sungguhan (bukan API publik resmi seperti ini), cek
dulu apakah pemanfaatannya diizinkan Terms of Service situs tersebut
sebelum melanjutkan -- prinsip ethical scraping yang sama tetap berlaku,
cuma mekanismenya beda (bukan robots.txt, tapi ToS & rate limit API).

Jalankan dengan:
    scrapy crawl api_products -O output/api_products.json
"""

import json
import scrapy
from datetime import datetime, timezone
from scrapy_spider.items import ProductItem


class ApiProductSpider(scrapy.Spider):
    name = "api_products"
    allowed_domains = ["fakestoreapi.com"]
    start_urls = ["https://fakestoreapi.com/products"]

    custom_settings = {
        # API biasanya bisa ditarik lebih cepat dari HTML scraping karena
        # payload jauh lebih ringan -- tapi tetap sopan, jangan spam.
        "DOWNLOAD_DELAY": 0.5,
    }

    def parse(self, response):
        """
        Berbeda dari spider HTML: di sini tidak ada CSS/XPath selector
        sama sekali. Response langsung di-parse sebagai JSON, lalu setiap
        elemen array dipetakan ke ProductItem.
        """
        try:
            products = json.loads(response.text)
        except json.JSONDecodeError as e:
            self.logger.error(f"Response bukan JSON valid: {e}")
            return

        self.logger.info(f"Menerima {len(products)} produk dari API")

        for product in products:
            item = ProductItem()
            item["url"] = f"https://fakestoreapi.com/products/{product.get('id')}"
            item["name"] = product.get("title")
            item["price_raw"] = str(product.get("price", ""))
            item["description"] = product.get("description")
            item["category"] = product.get("category")
            item["image_url"] = product.get("image")
            item["source_type"] = "api"

            # API ini tidak menyediakan rating/stok per item secara langsung
            # di endpoint utama (ada di endpoint terpisah /products/{id}
            # dengan struktur rating tersendiri di beberapa versi API) --
            # jadi field ini sengaja dikosongkan, bukan error.
            item["rating_raw"] = ""
            item["availability_raw"] = ""

            item["scraped_at"] = datetime.now(timezone.utc).isoformat()

            yield item
