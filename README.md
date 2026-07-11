# E-Commerce Scraper Pro

[![Tests](https://github.com/bahrul-dev/ecommerce-scraper-pro/actions/workflows/tests.yml/badge.svg)](https://github.com/bahrul-dev/ecommerce-scraper-pro/actions/workflows/tests.yml)

Production-grade web scraping pipeline yang mencakup seluruh spektrum kemampuan scraping profesional: HTML parsing (Scrapy), dynamic content (Selenium), API reverse-engineering, dual storage (relational + NoSQL), ethical scraping compliance, proxy rotation, production monitoring, distributed crawling (Redis), dan containerized deployment.

## Kenapa proyek ini dibuat

Proyek ini adalah evolusi dari beberapa scraper yang sudah pernah saya bangun sebelumnya (hotel database scraper, generator dealer OSINT scraper) — logic parsing/fallback/cleaning-nya reuse dari situ, tapi arsitekturnya dikembangkan bertahap untuk secara eksplisit menutup semua kategori kemampuan yang biasa dicari di role scraping profesional.

## Status kejujuran teknis

Proyek ini dikembangkan dengan prinsip: **setiap klaim kemampuan dibuktikan lewat test, dan yang belum bisa dibuktikan penuh dinyatakan jujur apa adanya** — bukan diklaim "selesai" begitu saja. Ringkasannya:

| Kemampuan | Status | Bukti |
|---|---|---|
| HTML scraping (Scrapy) | ✅ Teruji penuh, live-verified | 23 test, live crawl ke books.toscrape.com berhasil |
| Dynamic content (Selenium) | ⚠️ Logic teruji secara desain, belum live-run (butuh Chrome browser) | Kode + stealth options, belum ada test otomatis (tidak ada Chrome di CI) |
| API reverse-engineering | ✅ Teruji penuh (offline) | 5 test, belum live-test ke fakestoreapi.com sungguhan |
| Dual storage (PostgreSQL + MongoDB) | ✅ Teruji lewat unit test pipeline | Belum live-test dengan database sungguhan (butuh setup lokal) |
| Ethical scraping (robots.txt, rate limit, UA rotation) | ✅ Teruji penuh, **live-verified dengan insiden nyata** | Middleware pernah beneran memblokir situs yang robots.txt-nya melarang |
| Proxy rotation & anti-bot dasar | ✅ Teruji penuh (unit test) | 7 test, belum live-test dengan proxy sungguhan (butuh proxy provider) |
| Production monitoring | ✅ Teruji penuh, termasuk integrasi live | 10 unit test + 1 integration test yang benar-benar generate report saat crawl |
| Distributed crawling (Scrapy-Redis) | ✅ Teruji end-to-end dengan Redis sungguhan (1 worker) | 1 integration test; **belum diverifikasi dengan banyak worker paralel di mesin terpisah** |
| Cloud deployment (Docker) | ⚠️ Syntax tervalidasi, belum live-run | YAML valid, belum pernah `docker compose up` sungguhan (tidak ada Docker di environment dev) |

Baris ⚠️ bukan berarti tidak jalan — itu berarti "kodenya benar secara desain dan sudah divalidasi sejauh yang lingkungan development izinkan, tapi belum ada bukti live run penuh". Ini catatan yang sengaja dipertahankan sebagai bagian dari proyek, bukan disembunyikan.

## Fitur Utama

### 1. HTML scraping (Scrapy)
`scrapy_spider/spiders/ecommerce_spider.py` — spider dengan pagination, item pipeline, selector yang di-scope dengan benar (lihat catatan bug availability-scope di ARCHITECTURE.md).

### 2. API reverse-engineering
`scrapy_spider/spiders/api_spider.py` — mendemonstrasikan pola scraping alternatif: ambil data langsung dari endpoint JSON publik (fakestoreapi.com), bukan parsing HTML. Ini pola yang lebih stabil & lebih sering dipakai scraper profesional dibanding HTML parsing kalau situsnya menyediakan API.

### 3. Dynamic content scraping (Selenium)
`selenium_handler/dynamic_scraper.py` — infinite scroll/lazy-load handling, plus stealth options dasar (override `navigator.webdriver`, disable automation flags) untuk mengurangi deteksi bot paling umum.

### 4. Ethical scraping & anti-bot (`middlewares/`)
| Middleware | Fungsi |
|---|---|
| `robots_checker.py` | Cek & patuhi robots.txt per domain, fail-closed kalau tidak bisa diverifikasi |
| `rate_limiter.py` | Adaptive throttling — backoff otomatis kalau server merespons 429/503 |
| `user_agent_rotator.py` | Rotasi User-Agent browser mainstream |
| `proxy_rotator.py` | Rotasi proxy dengan health tracking (auto-cooldown proxy yang gagal terus), pass-through otomatis kalau tidak ada proxy dikonfigurasi |

### 5. Data cleaning & validasi (`data_cleaning/cleaner.py`)
Parsing harga/rating/stok, deduplikasi teks (menangani bug nyata yang ditemukan dari live scraping: deskripsi produk yang ter-render dobel), validasi field wajib.

### 6. Dual storage (`pipelines/`)
PostgreSQL (relational, upsert berbasis URL unik) dan MongoDB (NoSQL, schema fleksibel) berjalan paralel.

### 7. Production monitoring (`monitoring/health_check.py`)
Scrapy extension yang otomatis menulis laporan JSON tiap crawl selesai, dan mendeteksi anomali produksi umum: 0 item padahal ada request sukses (indikasi selector rusak), item di bawah ambang batas, robots.txt blocking, error rate tinggi. Bisa disambungkan ke webhook (Slack/Discord) untuk alert otomatis.

### 8. Distributed crawling (`scrapy_spider/spiders/ecommerce_distributed_spider.py`)
Versi Scrapy-Redis dari spider utama — scheduler & dedup filter disimpan di Redis, memungkinkan beberapa worker (proses/mesin berbeda) berbagi antrian crawling yang sama. Teruji end-to-end dengan Redis sungguhan.

### 9. Containerized deployment (`Dockerfile`, `docker-compose.yml`)
Stack lengkap (scraper + PostgreSQL + MongoDB + Redis) siap dijalankan dengan satu perintah `docker compose up`.

### 10. Automated testing (`tests/`)
**51 test** (unit + integration), sebagian besar jalan sepenuhnya offline tanpa dependency internet.

```bash
pytest tests/ -v
# 51 passed (1 skipped otomatis kalau Redis tidak tersedia)
```

## Struktur Proyek

```
ecommerce-scraper-pro/
├── scrapy_spider/
│   ├── spiders/
│   │   ├── ecommerce_spider.py            # spider HTML utama
│   │   ├── ecommerce_distributed_spider.py # versi Scrapy-Redis
│   │   ├── api_spider.py                  # spider via API JSON
│   │   └── base_ecommerce_parser.py       # shared parsing logic (mixin)
│   ├── items.py
│   └── settings.py
├── selenium_handler/dynamic_scraper.py
├── middlewares/
│   ├── robots_checker.py
│   ├── rate_limiter.py
│   ├── user_agent_rotator.py
│   └── proxy_rotator.py
├── monitoring/health_check.py             # production monitoring extension
├── pipelines/
│   ├── postgres_pipeline.py
│   └── mongodb_pipeline.py
├── data_cleaning/cleaner.py
├── scripts/preview_cleaned_data.py        # preview data cleaning tanpa DB
├── tests/                                  # 51 test
├── docs/ARCHITECTURE.md
├── Dockerfile
├── docker-compose.yml
├── .github/workflows/tests.yml            # CI otomatis (termasuk Redis)
├── requirements.txt
└── scrapy.cfg
```

## Cara Menjalankan

### Setup
```bash
pip install -r requirements.txt
```

> **Catatan kompatibilitas (Windows terutama):** `requirements.txt` mem-pin `twisted>=22.10.0,<24.7.0` karena Twisted 24.7+ menghapus fungsi internal yang masih dipakai Scrapy 2.11.2.

### Test (tidak butuh database/internet, Redis opsional)
```bash
pytest tests/ -v
```

### Scraping HTML biasa
```bash
scrapy crawl ecommerce -O output/products.json
```

### Scraping via API
```bash
scrapy crawl api_products -O output/api_products.json
```

### Preview data yang sudah dibersihkan (tanpa perlu database)
```bash
python scripts/preview_cleaned_data.py output/products.json
```

### Distributed crawling (butuh Redis)
```bash
redis-cli lpush ecommerce:start_urls "https://books.toscrape.com/"
scrapy crawl ecommerce_distributed   # jalankan di 1+ terminal/mesin
```

### Full stack dengan Docker
```bash
docker compose up -d postgres mongo redis
docker compose run scraper
```

## Target Demo

Spider HTML utama mengarah ke [books.toscrape.com](https://books.toscrape.com) — sandbox scraping resmi tanpa robots.txt (dikonfirmasi 404). Spider API mengarah ke [fakestoreapi.com](https://fakestoreapi.com) — REST API publik untuk testing/prototyping.

> **Catatan proses:** Versi awal proyek ini sempat mengarah ke `webscraper.io/test-sites/e-commerce`. Middleware `robots_checker.py` otomatis memblokirnya karena robots.txt situs itu memang melarang path tersebut — validasi nyata bahwa middleware ethical scraping bekerja benar, bukan kode kosmetik. Detail lengkap ada di `docs/ARCHITECTURE.md`.

## Catatan Teknis

Lihat [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) untuk detail keputusan desain, termasuk bug nyata yang ditemukan & diperbaiki lewat live-testing (bukan cuma asumsi dari dokumentasi).

---

**Dibangun oleh Mukhamad Bahrul Ulum** — Freelance Python Developer & Data Automation Specialist.
Proyek terkait: Hotel Database Scraper, Generator Dealer OSINT Scraper, TalentScan, SitusAkademik.
