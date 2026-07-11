"""
base_ecommerce_parser.py
---------------------------
Logic parsing HTML books.toscrape.com diekstrak ke mixin class terpisah
supaya bisa dipakai bareng oleh DUA jenis spider:
  1. EcommerceSpider (scrapy.Spider biasa, single-process)
  2. DistributedEcommerceSpider (RedisSpider, multi-worker via Redis)

Tanpa mixin ini, logic parsing harus di-copy-paste dua kali -- melanggar
prinsip DRY dan bikin fix bug harus dilakukan dua kali juga (seperti
availability scope bug yang sempat terjadi).
"""

from datetime import datetime, timezone
from scrapy_spider.items import ProductItem


class EcommerceParserMixin:
    """Mixin murni berisi method parse() dan parse_product() -- TIDAK
    mewarisi apapun dari scrapy.Spider, supaya bisa dikombinasikan
    dengan scrapy.Spider ATAU scrapy_redis.spiders.RedisSpider lewat
    multiple inheritance."""

    def parse(self, response):
        """Parse halaman listing buku, lalu follow ke tiap detail buku."""
        book_links = response.css("article.product_pod h3 a::attr(href)").getall()
        self.logger.info(f"Ditemukan {len(book_links)} buku di halaman ini")

        for link in book_links:
            yield response.follow(link, callback=self.parse_product)

        # Pagination: <li class="next"><a href="...">next</a></li>
        next_page = response.css("li.next a::attr(href)").get()
        if next_page:
            yield response.follow(next_page, callback=self.parse)

    def parse_product(self, response):
        """Parse detail halaman buku individual.

        PENTING: semua selector di bawah di-scope ke `div.product_main`
        (bukan langsung ke seluruh `response`). Ini karena halaman detail
        buku di books.toscrape.com juga menampilkan carousel "you may also
        like" di bagian bawah, yang isinya beberapa <article class="product_pod">
        lain -- masing-masing PUNYA elemen `p.instock.availability`,
        `p.star-rating`, dan `p.price_color` sendiri. Kalau selector tidak
        di-scope, data dari buku-buku rekomendasi itu ikut ke-scrape dan
        bercampur dengan data buku utama.
        """
        item = ProductItem()

        main = response.css("div.product_main")

        item["url"] = response.url
        item["name"] = main.css("h1::text").get()
        item["price_raw"] = main.css("p.price_color::text").get()
        item["description"] = response.css(
            "#product_description ~ p::text"
        ).get()

        item["rating_raw"] = main.css("p.star-rating::attr(class)").get() or ""

        item["availability_raw"] = " ".join(
            main.css("p.instock.availability::text").getall()
        ).strip()

        item["category"] = response.css(
            "ul.breadcrumb li:nth-child(3) a::text"
        ).get()

        item["scraped_at"] = datetime.now(timezone.utc).isoformat()

        yield item
