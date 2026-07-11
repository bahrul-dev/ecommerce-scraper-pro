# E-Commerce Scraper Pro

[![Tests](https://github.com/bahrul-dev/ecommerce-scraper-pro/actions/workflows/tests.yml/badge.svg)](https://github.com/bahrul-dev/ecommerce-scraper-pro/actions/workflows/tests.yml)

Production-grade web scraping pipeline untuk mengekstrak data produk e-commerce, dibangun untuk mendemonstrasikan praktik scraping yang scalable, reliable, dan bertanggung jawab (ethical scraping).

Dibangun sebagai showcase kemampuan yang mencakup: static & dynamic content scraping, dual storage (relational + NoSQL), ethical scraping compliance, dan automated testing tanpa dependency internet.

## Kenapa proyek ini dibuat

Proyek ini adalah evolusi dari beberapa scraper yang sudah pernah saya bangun sebelumnya (hotel database scraper, generator dealer OSINT scraper) — logic parsing/fallback/cleaning-nya reuse dari situ, tapi arsitekturnya di-refactor jadi lebih formal dan lengkap untuk menunjukkan:

1. Penggunaan **Scrapy** sebagai framework scraping formal (bukan cuma requests/BeautifulSoup script)
2. Dual storage: **PostgreSQL** (relational) dan **MongoDB** (NoSQL)
3. **Ethical scraping** — robots.txt compliance, rate limiting adaptif, retry/backoff
4. **Automated testing** — 16 test case (unit + integration), semua jalan offline

## Fitur Utama

### 1. Static content scraping (Scrapy)
- `scrapy_spider/spiders/ecommerce_spider.py` — spider dengan pagination handling & item pipeline
- Selector CSS terstruktur, hasil di-yield sebagai `ProductItem`

### 2. Dynamic content scraping (Selenium)
- `selenium_handler/dynamic_scraper.py` — handle infinite scroll / lazy-load
- Explicit wait (`WebDriverWait`), bukan `time.sleep()` statis, supaya stabil di berbagai kecepatan koneksi
- Headless Chrome dengan konfigurasi anti-crash (`--no-sandbox`, `--disable-dev-shm-usage`)

### 3. Ethical scraping (middlewares/)
| Middleware | Fungsi |
|---|---|
| `robots_checker.py` | Cek & patuhi robots.txt per domain sebelum request dieksekusi, dengan caching |
| `rate_limiter.py` | Adaptive throttling — delay naik otomatis (exponential backoff) kalau server merespons 429/503 |
| `user_agent_rotator.py` | Rotasi User-Agent browser mainstream, mencegah beban identitas request tunggal |

### 4. Data cleaning & validasi (`data_cleaning/cleaner.py`)
- Parsing harga, rating, review count dari teks mentah ke tipe data terstruktur
- Validasi field wajib — item invalid tidak diteruskan ke storage
- Testable secara terpisah dari proses scraping (unit test murni)

### 5. Dual storage (`pipelines/`)
- **PostgreSQL** (`postgres_pipeline.py`) — schema relational, upsert berdasarkan URL unik, cocok untuk query terstruktur & histori
- **MongoDB** (`mongodb_pipeline.py`) — schema fleksibel, cocok untuk data semi-terstruktur / arsip snapshot

### 6. Automated testing (`tests/`)
- 12 unit test untuk data cleaning (price/rating/review parsing, edge cases)
- 4 integration test yang menjalankan **full Scrapy crawl** (spider + middleware) terhadap local HTML fixture — **tidak butuh internet**, hasilnya reproducible di CI/CD manapun

```bash
pytest tests/ -v
# 16 passed
```

## Struktur Proyek

```
ecommerce-scraper-pro/
├── scrapy_spider/
│   ├── spiders/ecommerce_spider.py   # spider utama (static pages)
│   ├── items.py                      # schema data produk
│   └── settings.py                   # konfigurasi middleware & pipeline
├── selenium_handler/
│   └── dynamic_scraper.py            # handler dynamic/infinite-scroll content
├── middlewares/
│   ├── robots_checker.py             # ethical scraping: robots.txt compliance
│   ├── rate_limiter.py               # adaptive throttling + backoff
│   └── user_agent_rotator.py         # UA rotation
├── pipelines/
│   ├── postgres_pipeline.py          # relational storage
│   └── mongodb_pipeline.py           # NoSQL storage
├── data_cleaning/
│   └── cleaner.py                    # parsing & validasi data
├── tests/
│   ├── fixtures/                     # HTML sample untuk offline testing
│   ├── test_spider_offline.py        # spider override untuk test lokal
│   └── test_pipeline.py              # 16 test case (unit + integration)
├── docs/
│   └── ARCHITECTURE.md               # detail desain teknis & keputusan arsitektur
├── requirements.txt
└── scrapy.cfg
```

## Cara Menjalankan

### Setup
```bash
pip install -r requirements.txt
```

> **Catatan kompatibilitas (Windows terutama):** `requirements.txt` sengaja mem-pin versi `twisted` (`>=22.10.0,<24.7.0`). Twisted versi 24.7.0 ke atas menghapus fungsi internal yang masih dipakai Scrapy 2.11.2, menyebabkan `ImportError: cannot import name '_setAcceptableProtocols'`. Kalau lo install ulang dependency dan tetap ketemu error ini, cek dulu versi Twisted yang ter-install (`pip show twisted`) — kemungkinan ke-override oleh dependency lain.

### Jalankan test (tidak butuh database/internet)
```bash
pytest tests/ -v
```

### Jalankan scraping sungguhan (butuh PostgreSQL & MongoDB running)
```bash
export POSTGRES_DSN="dbname=ecommerce_scraper user=postgres password=postgres host=localhost port=5432"
export MONGO_URI="mongodb://localhost:27017"

scrapy crawl ecommerce -o output/products.json
```

### Dynamic content (infinite scroll)
```python
from selenium_handler.dynamic_scraper import scrape_infinite_scroll_page

products = scrape_infinite_scroll_page(
    "https://example.com/products",
    max_scrolls=10
)
```

## Target Demo

Spider mengarah ke [books.toscrape.com](https://books.toscrape.com) — sandbox scraping publik resmi yang dibuat oleh tim di balik Scrapy/Zyte, khusus untuk latihan web scraping. **Tidak ada file `robots.txt`** di situs ini (dikonfirmasi 404), artinya tidak ada pembatasan path sama sekali — aman untuk didemokan sepenuhnya tanpa isu legal/etika.

> **Catatan proses (kenapa bukan webscraper.io):** Versi awal proyek ini sempat mengarah ke `webscraper.io/test-sites/e-commerce`. Saat live-testing, middleware `robots_checker.py` secara otomatis memblokir scraping tersebut — dan setelah dicek, robots.txt situs itu memang secara eksplisit melarang path tersebut (`Disallow: /test-sites/e-commerce/`). Ini justru validasi nyata bahwa middleware ethical scraping bekerja dengan benar (bukan cuma kode kosmetik), dan jadi alasan proyek ini pindah target ke `books.toscrape.com` yang memang didesain tanpa pembatasan.

## Catatan Teknis

Lihat [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) untuk detail keputusan desain: kenapa dual storage, strategi retry/backoff, dan cara scale pipeline ini untuk volume data besar.

---

**Dibangun oleh Mukhamad Bahrul Ulum** — Freelance Python Developer & Data Automation Specialist.
Proyek terkait: Hotel Database Scraper, Generator Dealer OSINT Scraper, TalentScan, SitusAkademik.
