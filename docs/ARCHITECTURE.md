# Architecture & Design Decisions

Dokumen ini menjelaskan keputusan desain teknis di balik proyek ini — ditulis supaya reviewer (recruiter/tech lead) bisa menilai reasoning-nya, bukan cuma hasil akhirnya.

## 1. Kenapa Scrapy + Selenium, bukan salah satu saja?

Scrapy sangat efisien untuk static HTML (async request, built-in retry, item pipeline architecture) tapi tidak bisa mengeksekusi JavaScript. Selenium bisa handle dynamic content tapi jauh lebih berat secara resource (satu browser instance per session) dan tidak punya arsitektur pipeline built-in.

Keputusan: pakai Scrapy sebagai tulang punggung utama (listing, pagination, item pipeline), dan Selenium hanya dipanggil untuk kasus spesifik yang butuh JS execution (infinite scroll, lazy load). Ini pola yang sama dipakai di hotel scraper sebelumnya — Selenium untuk resolusi dynamic photo cascade di Booking.com/Expedia, requests-based untuk listing biasa.

## 2. Kenapa dual storage (PostgreSQL + MongoDB)?

Ini keputusan yang sengaja dibuat eksplisit untuk showcase, tapi juga punya alasan teknis riil:

- **PostgreSQL** cocok kalau data punya schema stabil dan butuh query relational (join dengan tabel kategori, histori harga per waktu, agregasi). Constraint `UNIQUE(url)` + upsert menjaga idempotency — re-run scraping tidak menghasilkan duplikat.
- **MongoDB** cocok untuk snapshot mentah / arsip historis, terutama kalau struktur produk bisa berubah-ubah antar situs (field spesifikasi produk yang beda-beda per kategori). Document-based storage tidak butuh migration schema setiap kali ada field baru.

Dalam praktik nyata (bukan cuma demo), tim biasanya pilih salah satu berdasarkan kebutuhan spesifik — proyek ini menunjukkan kemampuan bekerja dengan keduanya, bukan menyarankan keduanya selalu dipakai bersamaan.

## 3. Ethical scraping — kenapa 3 lapis (robots.txt + rate limiter + UA rotation)?

Tiga mekanisme ini saling melengkapi, bukan redundan:

| Mekanisme | Melindungi dari |
|---|---|
| `ROBOTSTXT_OBEY` + `robots_checker.py` | Melanggar preferensi eksplisit pemilik situs tentang path mana yang boleh di-crawl |
| `rate_limiter.py` (adaptive backoff) | Membebani server target — delay naik otomatis kalau server sudah menunjukkan tanda overload (429/503) |
| `user_agent_rotator.py` | Fingerprinting sederhana dari traffic otomatis massal dengan satu identitas UA |

Catatan penting: `robots_checker.py` menggunakan strategi **fail-closed** ketika robots.txt tidak bisa diverifikasi validitasnya secara aman (mis. situs mengembalikan 403 untuk request robots.txt) — di kasus ini middleware memilih untuk **tidak** melanjutkan scraping daripada mengasumsikan diizinkan. Ini konsisten dengan prinsip ethical scraping: kalau ragu, jangan crawl.

## 4. Kenapa integration test pakai local HTTP server, bukan live site?

Tiga alasan:

1. **Reliability** — test tidak boleh gagal hanya karena situs target down, berubah struktur HTML, atau rate-limit kita saat run test berkali-kali.
2. **Speed & CI/CD friendliness** — test yang butuh koneksi internet lambat dan tidak reproducible di environment CI yang mungkin punya restriksi network.
3. **Deterministic assertions** — dengan fixture HTML yang kita kontrol penuh, kita tahu persis berapa produk yang seharusnya ter-scrape dan field apa yang seharusnya ada, sehingga assertion test benar-benar bermakna (bukan "asal ada data").

Trade-off yang disadari: test ini tidak memverifikasi bahwa selector CSS masih valid terhadap struktur HTML situs asli saat ini (situs bisa berubah struktur). Untuk itu, tetap perlu smoke test manual berkala terhadap situs live sebelum deployment produksi.

## 5. Skalabilitas untuk volume besar

Beberapa keputusan desain yang mempersiapkan pipeline ini untuk scale:

- `CONCURRENT_REQUESTS_PER_DOMAIN` dibatasi (bukan unlimited) — mencegah pipeline "sukses tapi merusak" karena melanggar batas wajar ke satu domain.
- `AUTOTHROTTLE_ENABLED` — Scrapy otomatis menyesuaikan concurrency berdasarkan response time server, jadi tidak perlu tuning manual per situs.
- Pipeline storage menggunakan **upsert**, bukan insert biasa — penting untuk re-run pipeline secara terjadwal (cron/scheduler) tanpa membengkakkan storage dengan duplikat.
- Item pipeline terpisah dari parsing logic (spider hanya extract raw data, cleaning & validasi ada di modul terpisah) — memudahkan reuse logic yang sama untuk sumber data lain (mis. hasil dari Selenium handler juga bisa lewat `clean_product_record()` yang sama).

## 6. Kenapa target demo books.toscrape.com, bukan situs "e-commerce" literal?

Versi awal proyek ini menargetkan `webscraper.io/test-sites/e-commerce` (sandbox scraping dengan tema toko elektronik). Saat live-testing di lingkungan nyata, `robots_checker.py` memblokir seluruh request ke path tersebut. Setelah dicek langsung, robots.txt situs itu memang berisi:

```
User-agent: *
Disallow: /test-sites/e-commerce/
```

Path itu **secara eksplisit dilarang** untuk semua crawler. Ini adalah momen validasi yang bagus: middleware ethical scraping bekerja persis seperti seharusnya — menolak scraping yang memang dilarang pemilik situs, bukan cuma "kode yang keliatan aman tapi sebenarnya gak pernah diuji beneran".

Karena itu, target dipindah ke `books.toscrape.com` — sandbox scraping resmi (dibuat oleh tim di balik Scrapy/Zyte) yang tidak memiliki file robots.txt sama sekali (404), sehingga tidak ada pembatasan path apapun. Situs ini tetap merepresentasikan pola e-commerce (listing produk, harga, rating, status stok, kategori, pagination), jadi tujuan showcase teknis tidak berubah — hanya target yang lebih tepat secara etika.

**Pelajaran untuk kasus nyata:** kalau proyek ini di-generalize ke situs e-commerce sungguhan (bukan sandbox), langkah pertama sebelum menulis satu baris selector pun adalah mengecek robots.txt situs target dan hanya melanjutkan ke path yang diizinkan.

## 8. Bug yang ditemukan & diperbaiki lewat live-testing sungguhan

Dua masalah data quality baru ketahuan setelah live crawl beneran dijalankan (bukan cuma test dengan fixture) -- ini contoh nyata kenapa smoke test manual terhadap situs live tetap perlu, walau sudah ada automated test:

**a) Selector `availability` bocor mengambil data dari carousel "you may also like".**
Halaman detail buku di books.toscrape.com menampilkan rekomendasi buku lain di bagian bawah, masing-masing punya elemen `p.instock.availability` sendiri. Selector awal tidak di-scope ke container utama (`div.product_main`) dan memakai `.getall()`, sehingga status stok dari beberapa buku rekomendasi ikut tergabung jadi satu string. Fix: semua selector field produk di-scope eksplisit ke `div.product_main`, dan `.getall()` diganti `.get()` untuk mengambil satu match saja.

**b) Beberapa deskripsi produk ter-render dua kali dalam satu text node.**
Ditemukan dari data live: teks deskripsi pada sebagian buku muncul berulang persis dari awal, di dalam SATU elemen HTML yang sama (bukan karena selector mengambil elemen yang salah -- `#product_description` adalah ID unik). Kemungkinan ini sisa markup versi lama fitur "read more" di situs. Karena ini murni soal *isi* data, bukan soal ketepatan selector, fix-nya diletakkan di layer cleaning (`dedupe_repeated_text()`), bukan di spider -- prinsip pemisahan tanggung jawab yang sama yang dipakai di keputusan desain awal (spider hanya extract raw data, semua normalisasi ada di `data_cleaning/`).

**Pelajaran:** integration test dengan fixture (poin 4) membuktikan *mekanisme* pipeline bekerja benar, tapi tidak bisa menjamin *selector* selalu 100% presisi terhadap variasi konten situs live yang sesungguhnya -- termasuk halaman produk yang menampilkan modul lain (carousel, related items) atau anomali konten. Kombinasi automated test + smoke test live tetap diperlukan.

## 9. Lima kemampuan tambahan: kenapa dan bagaimana diverifikasi

Bagian ini didokumentasikan terpisah karena masing-masing punya tingkat verifikasi yang berbeda -- prinsip proyek ini adalah jujur soal mana yang teruji penuh vs mana yang "benar secara desain, belum live-verified".

**a) API reverse-engineering (`api_spider.py`)**
Sebelum menulis satu CSS selector pun untuk situs baru, langkah profesional pertama adalah cek DevTools > Network > filter XHR/Fetch -- apakah situs memuat data lewat API internal? Kalau ya, scraping API jauh lebih stabil (tidak rusak kalau HTML/CSS situs berubah) dan lebih ringan. Spider ini didemonstrasikan lewat `fakestoreapi.com` (API publik resmi untuk testing, bukan reverse-engineering situs privat). Diuji penuh offline (5 test) dengan fixture JSON lokal.

**b) Proxy rotation (`proxy_rotator.py`)**
Middleware pass-through by default (tidak butuh proxy untuk proyek jalan), tapi siap dipakai production dengan menambahkan `PROXY_LIST`. Health tracking (auto-cooldown proxy yang gagal berturut-turut) diuji lewat 7 unit test dengan mock request/response -- TIDAK diuji dengan proxy sungguhan karena itu butuh layanan proxy berbayar/pihak ketiga di luar cakupan proyek demo ini.

**c) Production monitoring (`monitoring/health_check.py`)**
Extension ini yang paling "membuktikan diri sendiri" -- deteksi anomalinya sempat langsung teraktivasi beneran saat debugging distributed spider (menangkap kasus `ZERO_ITEMS` waktu local test server sempat mati). Report JSON terstruktur dibuat tiap crawl selesai, siap disambungkan ke dashboard (Grafana+Loki) kalau di-scale. Pengiriman webhook alert sudah diimplementasi tapi belum diuji end-to-end (butuh URL Slack/Discord sungguhan).

**d) Distributed crawling (`ecommerce_distributed_spider.py`)**
Dibangun di atas `scrapy-redis`. Diuji end-to-end dengan Redis sungguhan (`redis-server` lokal) -- scheduler dan dedup filter terbukti benar-benar menggunakan Redis (`scheduler/dequeued/redis` di stats), bukan cuma dikonfigurasi tanpa efek. **Batasan verifikasi:** test yang ada membuktikan SATU worker bekerja benar dengan Redis backend. Skenario BANYAK worker paralel di mesin berbeda (use case sesungguhnya dari distributed crawling) belum diverifikasi karena butuh infrastruktur multi-mesin yang di luar cakupan environment pengembangan ini. Logic-nya seharusnya scale sesuai desain scrapy-redis (dipakai luas di industri), tapi klaim itu belum dibuktikan sendiri di proyek ini.

**e) Containerized deployment (`Dockerfile`, `docker-compose.yml`)**
Syntax YAML dan Dockerfile sudah divalidasi (`docker compose config` setara parsing), tapi belum pernah dijalankan (`docker compose up`) end-to-end karena tidak ada Docker daemon di environment pengembangan proyek ini. Sebelum dipakai deployment produksi sungguhan, wajib diverifikasi dulu di mesin yang punya Docker.

**Kenapa perbedaan level verifikasi ini penting didokumentasikan:** supaya siapa pun yang membaca proyek ini (termasuk reviewer teknis) tahu persis bagian mana yang bisa dipercaya penuh dan bagian mana yang perlu diverifikasi ulang sebelum dipakai di produksi sungguhan. Ini juga alasan kenapa proyek ini punya CI (`.github/workflows/tests.yml`) yang menyediakan Redis service -- supaya klaim "teruji" tetap valid tiap kali ada perubahan kode, bukan cuma benar sekali waktu ditulis.

## 10. Yang sengaja belum dibangun (scope boundary)

Setelah penambahan proxy rotation, monitoring, dan distributed crawling, boundary yang tersisa:

- **Anti-bot tingkat lanjut** (bypass Cloudflare/DataDome/PerimeterX, CAPTCHA solving, browser fingerprint spoofing penuh) — proxy rotation dan Selenium stealth dasar yang ada di proyek ini menangani kasus umum, tapi tidak dirancang untuk melawan sistem anti-bot komersial tingkat tinggi. Itu butuh proxy residensial premium dan teknik yang berada di luar cakupan proyek portfolio ini secara sengaja.
- **Scheduler/orchestration** (Airflow/Celery) — proyek ini punya distributed crawling (Scrapy-Redis) untuk scale horizontal, tapi belum ada scheduling terjadwal (mis. "crawl tiap 6 jam otomatis"). Itu layer terpisah yang bisa ditambahkan di atas (mis. cron job yang trigger `docker compose run scraper`, atau Airflow DAG).
- **Dashboard visual monitoring** — `health_check.py` menghasilkan data terstruktur (JSON report per run) yang siap dikonsumsi dashboard, tapi belum ada dashboard visual (Grafana) yang benar-benar terhubung. Datanya sudah ada, visualisasinya belum.
- **Multi-worker distributed crawling di banyak mesin sungguhan** — lihat poin (d) di atas, ini bukan "belum dibangun" tapi "dibangun, belum diverifikasi di skala penuh".
