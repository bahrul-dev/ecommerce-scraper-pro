# Dockerfile
# ------------
# Image untuk menjalankan scraper ini di lingkungan container/cloud.
# Base image Python slim (bukan full) supaya ukuran image lebih kecil --
# penting kalau di-deploy ke platform yang charge per-storage/transfer.

FROM python:3.12-slim

WORKDIR /app

# Dependency sistem yang dibutuhkan Scrapy (lxml perlu libxml2) dan
# Selenium (Chromium headless untuk dynamic scraping).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2-dev \
    libxslt1-dev \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium
ENV CHROMEDRIVER_PATH=/usr/bin/chromedriver

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user -- praktik keamanan dasar, jangan jalankan container
# sebagai root kalau tidak perlu.
RUN useradd --create-home scraper && chown -R scraper:scraper /app
USER scraper

# Default command: jalankan spider utama. Override dengan `docker run
# <image> scrapy crawl <spider_lain>` untuk spider lain (mis. api_products,
# ecommerce_distributed).
CMD ["scrapy", "crawl", "ecommerce", "-O", "output/products.json"]
