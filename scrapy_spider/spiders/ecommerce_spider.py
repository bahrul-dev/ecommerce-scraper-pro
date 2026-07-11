"""
ecommerce_spider.py
--------------------
Spider Scrapy untuk mengambil data produk (buku) dari books.toscrape.com --
sandbox scraping publik resmi yang dibuat oleh tim di balik Scrapy/Zyte,
khusus untuk latihan web scraping. TIDAK ADA file robots.txt di situs ini
(dikonfirmasi 404), artinya tidak ada pembatasan path -- aman untuk
didemokan sepenuhnya tanpa isu legal/etika.

Alur:
1. Mulai dari halaman utama katalog (listing semua buku, dengan pagination).
2. Ikuti link tiap buku ke halaman detailnya.
3. Ambil field: judul, harga, rating (bintang), status stok, deskripsi,
   kategori.
4. Data dikirim ke item pipeline untuk dibersihkan & disimpan
   (PostgreSQL + MongoDB).

Jalankan dengan:
    scrapy crawl ecommerce -O output/products.json

NOTE: gunakan -O (uppercase, overwrite) bukan -o (lowercase, append).
Kalau pakai -o dan menjalankan crawl berkali-kali ke file yang sama,
hasilnya adalah JSON yang tidak valid karena Scrapy menambahkan array
baru ke belakang file lama alih-alih menimpanya.
"""

import scrapy
from datetime import datetime, timezone
from scrapy_spider.items import ProductItem


class EcommerceSpider(scrapy.Spider):
    name = "ecommerce"
    allowed_domains = ["books.toscrape.com"]
    start_urls = ["https://books.toscrape.com/"]

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
    }

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
        bercampur dengan data buku utama (ini bug yang sempat kejadian:
        `availability_raw` berisi teks "In stock" berulang-ulang karena
        ke-gabung dari beberapa buku sekaligus).
        """
        item = ProductItem()

        main = response.css("div.product_main")

        item["url"] = response.url
        item["name"] = main.css("h1::text").get()
        item["price_raw"] = main.css("p.price_color::text").get()
        item["description"] = response.css(
            "#product_description ~ p::text"
        ).get()

        # Rating disimpan sebagai class CSS: <p class="star-rating Three">
        item["rating_raw"] = main.css("p.star-rating::attr(class)").get() or ""

        # .getall() (bukan .get()) -- perlu ambil SEMUA text node dari
        # SATU elemen p.instock.availability ini (teksnya terpecah jadi
        # beberapa text node oleh tag <i class="icon-ok"></i> di
        # tengahnya: " " sebelum ikon, lalu "In stock (x available)"
        # sesudah ikon). Karena sudah di-scope ke `main`, getall() di
        # sini AMAN -- tidak akan ikut ambil dari carousel produk lain
        # seperti bug sebelumnya, karena hanya ada SATU elemen match
        # dalam scope div.product_main.
        item["availability_raw"] = " ".join(
            main.css("p.instock.availability::text").getall()
        ).strip()

        item["category"] = response.css(
            "ul.breadcrumb li:nth-child(3) a::text"
        ).get()

        item["scraped_at"] = datetime.now(timezone.utc).isoformat()

        yield item
