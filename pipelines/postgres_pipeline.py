"""
postgres_pipeline.py
---------------------
Scrapy item pipeline untuk menyimpan produk yang sudah dibersihkan
ke PostgreSQL (relational storage). Dipakai untuk data yang butuh
integritas relasional & query terstruktur (mis. join dengan tabel
kategori, histori harga per waktu, dsb).

Skema tabel:
    products (
        id SERIAL PRIMARY KEY,
        url TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        price NUMERIC(10,2),
        rating NUMERIC(2,1),
        in_stock BOOLEAN,
        stock_quantity INTEGER,
        category TEXT,
        scraped_at TIMESTAMP
    )

Konfigurasi koneksi diambil dari environment variable supaya credential
tidak hardcode di kode (best practice keamanan dasar).
"""

import os
import logging
import psycopg2

from data_cleaning.cleaner import clean_product_record

logger = logging.getLogger("postgres_pipeline")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    price NUMERIC(10,2),
    rating NUMERIC(2,1),
    in_stock BOOLEAN,
    stock_quantity INTEGER,
    category TEXT,
    scraped_at TIMESTAMP,
    inserted_at TIMESTAMP DEFAULT NOW()
);
"""

UPSERT_SQL = """
INSERT INTO products (url, name, description, price, rating, in_stock, stock_quantity, category, scraped_at)
VALUES (%(url)s, %(name)s, %(description)s, %(price)s, %(rating)s, %(in_stock)s, %(stock_quantity)s, %(category)s, %(scraped_at)s)
ON CONFLICT (url) DO UPDATE SET
    name = EXCLUDED.name,
    description = EXCLUDED.description,
    price = EXCLUDED.price,
    rating = EXCLUDED.rating,
    in_stock = EXCLUDED.in_stock,
    stock_quantity = EXCLUDED.stock_quantity,
    category = EXCLUDED.category,
    scraped_at = EXCLUDED.scraped_at;
"""


class PostgresPipeline:
    def __init__(self):
        self.conn = None
        self.cursor = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        dsn = os.environ.get(
            "POSTGRES_DSN",
            "dbname=ecommerce_scraper user=postgres password=postgres host=localhost port=5432",
        )
        try:
            self.conn = psycopg2.connect(dsn)
            self.cursor = self.conn.cursor()
            self.cursor.execute(CREATE_TABLE_SQL)
            self.conn.commit()
            logger.info("Terhubung ke PostgreSQL dan tabel siap.")
        except Exception as e:
            logger.error(f"Gagal konek PostgreSQL: {e}")
            self.conn = None

    def close_spider(self, spider):
        if self.conn:
            self.cursor.close()
            self.conn.close()

    def process_item(self, item, spider):
        if not self.conn:
            return item  # Storage gagal konek -> tetap lanjutkan pipeline lain

        result = clean_product_record(dict(item))
        if not result.is_valid:
            logger.warning(f"Item di-skip (invalid): {result.errors}")
            return item

        try:
            self.cursor.execute(UPSERT_SQL, result.cleaned)
            self.conn.commit()
        except Exception as e:
            logger.error(f"Gagal insert ke Postgres: {e}")
            self.conn.rollback()

        return item
