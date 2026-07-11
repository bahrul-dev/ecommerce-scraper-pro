"""
items.py
--------
Definisi struktur data (item) yang diambil dari setiap produk (buku).
Dipisahkan dari spider supaya schema jelas & bisa dipakai ulang
oleh pipeline (cleaning, storage) tanpa perlu tahu detail parsing HTML.

Field disesuaikan dengan struktur nyata books.toscrape.com:
- rating ditampilkan sebagai KATA di class CSS ("One".."Five"), bukan angka
- tidak ada review_count, diganti availability (stok)
"""

import scrapy


class ProductItem(scrapy.Item):
    url = scrapy.Field()
    name = scrapy.Field()
    price_raw = scrapy.Field()
    description = scrapy.Field()
    rating_raw = scrapy.Field()          # mis. "star-rating Three"
    availability_raw = scrapy.Field()    # mis. "In stock (22 available)"
    category = scrapy.Field()
    scraped_at = scrapy.Field()

    # Field hasil cleaning (diisi oleh data_cleaning pipeline)
    price_clean = scrapy.Field()
    rating_clean = scrapy.Field()
    availability_clean = scrapy.Field()
