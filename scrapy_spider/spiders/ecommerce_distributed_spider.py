"""
ecommerce_distributed_spider.py
----------------------------------
Versi DISTRIBUTED dari EcommerceSpider, dibangun di atas scrapy-redis.
Beda mendasar dari spider biasa:

  - Spider biasa: satu proses, start_urls ditentukan di kode, dedup
    request disimpan di memory proses itu sendiri.
  - Spider ini: start URL diambil dari Redis (bisa dimasukkan dari luar,
    kapan saja, oleh proses manapun), scheduler & dedup filter juga
    disimpan di Redis -- artinya BEBERAPA worker (proses/mesin berbeda)
    bisa menjalankan spider dengan nama yang sama secara BERSAMAAN,
    saling berbagi antrian URL yang sama tanpa scraping URL yang
    sama dua kali.

Ini pola yang dipakai kalau volume crawling terlalu besar untuk
ditangani satu proses/mesin (jutaan halaman, perlu di-scale horizontal).

CARA JALANKAN (butuh Redis running):
    1. Masukkan start URL ke Redis:
       redis-cli lpush ecommerce:start_urls "https://books.toscrape.com/"

    2. Jalankan satu atau LEBIH worker (di terminal/mesin berbeda),
       masing-masing dengan command yang SAMA persis:
       scrapy crawl ecommerce_distributed

    Worker-worker itu otomatis berbagi antrian lewat Redis -- tidak
    perlu koordinasi manual. Matikan (Ctrl+C) semua worker kapan saja;
    redis-key SCHEDULER_PERSIST=True membuat antrian tetap tersimpan,
    bisa dilanjut nanti.

CATATAN KEJUJURAN TEKNIS: pola ini sudah diverifikasi jalan di sandbox
dev (redis lokal, 1 worker, lihat tests/test_distributed_spider.py).
Yang BELUM diverifikasi: perilaku dengan BANYAK worker paralel
sungguhan di mesin terpisah -- itu butuh infrastruktur multi-mesin
yang di luar cakupan environment testing ini. Secara teori (dan sesuai
dokumentasi resmi scrapy-redis) pola ini scale secara linear, tapi
klaim itu belum divalidasi dengan benchmark sungguhan di proyek ini.
"""

from scrapy_redis.spiders import RedisSpider
from scrapy_spider.spiders.base_ecommerce_parser import EcommerceParserMixin


class DistributedEcommerceSpider(EcommerceParserMixin, RedisSpider):
    name = "ecommerce_distributed"
    allowed_domains = ["books.toscrape.com"]

    # Key Redis tempat start URL diambil. Beberapa worker dengan `name`
    # yang sama otomatis "mendengarkan" key yang sama ini.
    redis_key = "ecommerce:start_urls"

    custom_settings = {
        "DOWNLOAD_DELAY": 1.0,
        # Scheduler & dedup filter disimpan di Redis, bukan memory lokal
        # -- ini yang memungkinkan multi-worker berbagi antrian.
        "SCHEDULER": "scrapy_redis.scheduler.Scheduler",
        "DUPEFILTER_CLASS": "scrapy_redis.dupefilter.RFPDupeFilter",
        # Antrian TETAP ada di Redis walau semua worker berhenti --
        # bisa dilanjutkan nanti tanpa kehilangan progress.
        "SCHEDULER_PERSIST": True,
        "REDIS_URL": "redis://localhost:6379",
    }
