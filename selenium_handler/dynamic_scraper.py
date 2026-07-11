"""
dynamic_scraper.py
--------------------
Handler Selenium untuk mengambil konten yang di-render lewat JavaScript
(bukan tersedia langsung di HTML awal) -- misalnya varian test-site
e-commerce yang pakai infinite scroll / "Load More" button.

Ini melengkapi Scrapy spider: Scrapy dipakai untuk halaman statis/listing
biasa, sedangkan modul ini dipakai untuk kasus di mana produk baru
di-load setelah interaksi JS (scroll, klik tombol) -- pola yang sama
seperti yang sudah pernah ditangani di proyek hotel scraper (Booking.com
dynamic photo cascade, Expedia lazy-load).

Desain: headless Chrome + explicit wait (bukan time.sleep statis) supaya
lebih stabil terhadap variasi kecepatan load halaman.
"""

import logging
import time
from typing import List, Dict

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger("dynamic_scraper")


def build_driver(headless: bool = True) -> webdriver.Chrome:
    """
    Konfigurasi Chrome driver dengan opsi stealth DASAR -- mengurangi
    sinyal paling umum yang dipakai situs untuk mendeteksi browser
    otomatis (bukan bypass anti-bot canggih seperti Cloudflare/DataDome,
    itu di luar cakupan proyek ini secara sengaja, lihat ARCHITECTURE.md).

    Yang dilakukan di sini:
      1. Menyembunyikan flag `navigator.webdriver` (indikator paling
         umum dicek situs untuk tahu browser dikendalikan otomasi)
      2. Mematikan fitur automation Chrome yang bocor lewat DevTools
         Protocol (`enable-automation` switch)
      3. User-Agent browser asli (bukan default Selenium yang beda dari
         Chrome biasa)
    """
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
    )

    # Stealth dasar: hilangkan flag yang menandakan Chrome dikendalikan
    # otomasi (bukan bypass anti-bot canggih, cuma menghindari deteksi
    # paling naif/umum)
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)

    driver = webdriver.Chrome(options=options)

    # navigator.webdriver secara default bernilai True di browser yang
    # dikendalikan Selenium -- banyak situs cek nilai ini untuk deteksi
    # bot paling sederhana. Baris ini override jadi undefined lewat CDP,
    # sebelum halaman apapun dimuat.
    driver.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        },
    )

    return driver


def scrape_infinite_scroll_page(
    url: str,
    max_scrolls: int = 10,
    scroll_pause: float = 1.5,
    headless: bool = True,
) -> List[Dict]:
    """
    Buka halaman, scroll bertahap sampai tidak ada produk baru yang
    muncul atau max_scrolls tercapai, lalu ekstrak semua produk yang
    sudah ter-render.
    """
    driver = build_driver(headless=headless)
    products = []

    try:
        driver.get(url)
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div.thumbnail"))
        )

        last_count = 0
        for scroll_attempt in range(max_scrolls):
            driver.execute_script(
                "window.scrollTo(0, document.body.scrollHeight);"
            )
            time.sleep(scroll_pause)

            current_items = driver.find_elements(By.CSS_SELECTOR, "div.thumbnail")
            current_count = len(current_items)

            logger.info(
                f"Scroll #{scroll_attempt + 1}: {current_count} produk terlihat"
            )

            if current_count == last_count:
                logger.info("Tidak ada produk baru, berhenti scroll.")
                break
            last_count = current_count

        # Ekstrak semua produk yang sudah ter-render di DOM
        items = driver.find_elements(By.CSS_SELECTOR, "div.thumbnail")
        for el in items:
            try:
                name = el.find_element(By.CSS_SELECTOR, "a.title").get_attribute(
                    "title"
                )
                price = el.find_element(By.CSS_SELECTOR, "h4.price").text
                url_href = el.find_element(By.CSS_SELECTOR, "a.title").get_attribute(
                    "href"
                )
                products.append(
                    {
                        "name": name,
                        "price_raw": price,
                        "url": url_href,
                        "scraped_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
                    }
                )
            except Exception as e:
                logger.warning(f"Gagal parse satu item: {e}")
                continue

    except TimeoutException:
        logger.error(f"Timeout menunggu elemen produk di {url}")
    finally:
        driver.quit()

    return products
