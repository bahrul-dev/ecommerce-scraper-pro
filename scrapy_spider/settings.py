# settings.py
# Konfigurasi utama proyek Scrapy. Menggabungkan:
# - Middleware ethical scraping (robots checker, rate limiter, UA rotator)
# - Pipeline dual-storage (PostgreSQL + MongoDB)
# - AutoThrottle bawaan Scrapy sebagai lapisan tambahan (bukan pengganti
#   rate_limiter custom, tapi saling melengkapi)

BOT_NAME = "ecommerce_scraper_pro"

SPIDER_MODULES = ["scrapy_spider.spiders"]
NEWSPIDER_MODULE = "scrapy_spider.spiders"

USER_AGENT = "EcommerceScraperPro/1.0 (+portfolio-project; contact: walashri@example.com)"

# --- Ethical scraping: patuhi robots.txt secara default ---
ROBOTSTXT_OBEY = True  # Scrapy built-in check
# Middleware custom di bawah ini jadi lapisan kedua yang lebih eksplisit/loggable

DOWNLOADER_MIDDLEWARES = {
    "middlewares.robots_checker.RobotsComplianceMiddleware": 100,
    "middlewares.proxy_rotator.ProxyRotatorMiddleware": 150,
    "middlewares.user_agent_rotator.UserAgentRotatorMiddleware": 200,
    "middlewares.rate_limiter.AdaptiveRateLimiterMiddleware": 300,
}

# Daftar proxy opsional, format: ["http://user:pass@host:port", ...]
# Kosong secara default -- middleware otomatis pass-through tanpa proxy.
# Bisa juga diisi lewat environment variable PROXY_LIST (dipisah koma).
PROXY_LIST = []

ITEM_PIPELINES = {
    "pipelines.postgres_pipeline.PostgresPipeline": 300,
    "pipelines.mongodb_pipeline.MongoDBPipeline": 400,
}

# --- Rate limiting bawaan Scrapy (lapisan tambahan) ---
DOWNLOAD_DELAY = 1.0
RANDOMIZE_DOWNLOAD_DELAY = True
CONCURRENT_REQUESTS_PER_DOMAIN = 4

AUTOTHROTTLE_ENABLED = True
AUTOTHROTTLE_START_DELAY = 1.0
AUTOTHROTTLE_MAX_DELAY = 30.0
AUTOTHROTTLE_TARGET_CONCURRENCY = 2.0

# --- Retry policy ---
RETRY_ENABLED = True
RETRY_TIMES = 3
RETRY_HTTP_CODES = [500, 502, 503, 504, 408, 429]

# --- Production monitoring ---
EXTENSIONS = {
    "monitoring.health_check.ScraperHealthMonitor": 500,
}
# Ambang batas minimal item -- kalau hasil crawl di bawah ini, dianggap
# anomali (0 = tidak dicek, karena tiap situs punya jumlah wajar beda-beda)
MONITORING_MIN_EXPECTED_ITEMS = 0
MONITORING_REPORT_DIR = "output/monitoring"
# Isi dengan URL webhook (Slack/Discord/dsb) kalau mau alert otomatis.
# Kosong = alert cuma masuk log level CRITICAL.
MONITORING_WEBHOOK_URL = None

# --- Logging ---
LOG_LEVEL = "INFO"

# --- Export encoding ---
FEED_EXPORT_ENCODING = "utf-8"
