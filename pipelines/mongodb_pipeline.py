"""
mongodb_pipeline.py
---------------------
Scrapy item pipeline untuk menyimpan produk ke MongoDB (NoSQL storage).

Alasan pakai NoSQL di samping PostgreSQL:
- Struktur data hasil scraping sering berubah-ubah per situs (field
  tambahan, nested spec produk, dsb) -- MongoDB lebih fleksibel untuk
  data semi-terstruktur seperti ini dibanding relational strict schema.
- Cocok untuk raw snapshot / arsip historis tiap kali scraping jalan,
  tanpa perlu migration schema.

Koleksi: ecommerce_scraper.products
Index unik di field "url" supaya upsert idempotent (re-run scraping
tidak menghasilkan duplikat).
"""

import os
import logging
from datetime import datetime, timezone

from pymongo import MongoClient, UpdateOne
from pymongo.errors import PyMongoError

from data_cleaning.cleaner import clean_product_record

logger = logging.getLogger("mongodb_pipeline")


class MongoDBPipeline:
    def __init__(self):
        self.client = None
        self.db = None
        self.collection = None

    @classmethod
    def from_crawler(cls, crawler):
        return cls()

    def open_spider(self, spider):
        uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        db_name = os.environ.get("MONGO_DB", "ecommerce_scraper")
        try:
            self.client = MongoClient(uri, serverSelectionTimeoutMS=5000)
            self.client.server_info()  # trigger koneksi, cepat gagal kalau down
            self.db = self.client[db_name]
            self.collection = self.db["products"]
            self.collection.create_index("url", unique=True)
            logger.info(f"Terhubung ke MongoDB: {db_name}.products")
        except PyMongoError as e:
            logger.error(f"Gagal konek MongoDB: {e}")
            self.client = None

    def close_spider(self, spider):
        if self.client:
            self.client.close()

    def process_item(self, item, spider):
        if self.client is None:
            return item

        result = clean_product_record(dict(item))
        if not result.is_valid:
            logger.warning(f"Item di-skip (invalid) untuk Mongo: {result.errors}")
            return item

        doc = result.cleaned
        doc["updated_at"] = datetime.now(timezone.utc)

        try:
            self.collection.bulk_write(
                [
                    UpdateOne(
                        {"url": doc["url"]},
                        {"$set": doc},
                        upsert=True,
                    )
                ]
            )
        except PyMongoError as e:
            logger.error(f"Gagal upsert ke MongoDB: {e}")

        return item
