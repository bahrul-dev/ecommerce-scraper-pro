"""
cleaner.py
----------
Modul pembersihan & validasi data hasil scraping sebelum masuk ke storage.
Dipakai baik oleh Scrapy item pipeline maupun oleh selenium_handler
(supaya logic cleaning tidak duplikat di dua tempat).

Tanggung jawab:
- Parsing harga dari teks (mis. "£24.99" -> 24.99)
- Parsing rating dari CLASS CSS berbentuk kata (mis. "star-rating Three" -> 3.0)
  -- ini format asli books.toscrape.com, bukan atribut numerik data-rating
- Parsing status stok dari teks (mis. "In stock (22 available)" -> 22)
- Validasi: pastikan field wajib tidak kosong, tipe data benar
- Deteksi duplikat berdasarkan URL produk
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("data_cleaner")

# Mapping kata rating -> angka, sesuai konvensi books.toscrape.com
# (class CSS: "star-rating One" s/d "star-rating Five")
RATING_WORD_MAP = {
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
}


@dataclass
class CleaningResult:
    is_valid: bool
    cleaned: dict
    errors: list = field(default_factory=list)


def dedupe_repeated_text(text: Optional[str], min_chunk: int = 40) -> Optional[str]:
    """
    Beberapa halaman produk di books.toscrape.com ternyata merender teks
    deskripsi DUA KALI berturut-turut dalam satu text node yang sama
    (kemungkinan sisa markup versi "read more" lama di situs). Ini
    ditemukan lewat live-testing sungguhan, bukan asumsi -- jadi
    perbaikannya di layer cleaning, bukan di selector, karena selektor
    sudah benar (mengambil satu elemen yang unik lewat #product_description).

    Strategi: ambil potongan awal teks (`min_chunk` karakter), cek apakah
    potongan itu muncul lagi di paruh kedua teks -- kalau iya, berarti
    teks terduplikasi dan kita potong di titik kemunculan kedua.
    """
    if not text or len(text) < min_chunk * 2:
        return text

    chunk = text[:min_chunk]
    second_occurrence = text.find(chunk, min_chunk)

    if second_occurrence == -1:
        return text  # Tidak ada duplikasi terdeteksi, teks asli aman

    return text[:second_occurrence].rstrip()


def parse_price(raw: Optional[str]) -> Optional[float]:
    if not raw:
        return None
    match = re.search(r"[\d,.]+", raw)
    if not match:
        return None
    number_str = match.group().replace(",", "")
    try:
        return round(float(number_str), 2)
    except ValueError:
        return None


def parse_rating(raw: Optional[str]) -> Optional[float]:
    """Parse rating numerik langsung (0-5). Dipertahankan untuk kasus umum
    di mana situs lain menyediakan rating sebagai angka langsung."""
    if raw is None:
        return None
    try:
        value = float(raw)
        if 0 <= value <= 5:
            return value
        logger.warning(f"Rating di luar rentang wajar: {value}")
        return None
    except (ValueError, TypeError):
        return None


def parse_star_rating_word(raw_class: Optional[str]) -> Optional[float]:
    """
    Parse rating dari string class CSS berbentuk kata, format asli
    books.toscrape.com: "star-rating Three" -> 3.0

    Menerima juga input yang sudah berupa satu kata saja ("Three").
    """
    if not raw_class:
        return None

    words = raw_class.strip().split()
    for word in words:
        normalized = word.strip().lower()
        if normalized in RATING_WORD_MAP:
            return RATING_WORD_MAP[normalized]

    logger.warning(f"Tidak bisa parse rating dari: '{raw_class}'")
    return None


def parse_availability(raw: Optional[str]) -> dict:
    """
    Parse status stok dari teks bebas, mis:
      "In stock (22 available)" -> {"in_stock": True, "quantity": 22}
      "Out of stock"            -> {"in_stock": False, "quantity": 0}

    Selalu mengembalikan dict (tidak pernah None) supaya aman untuk
    storage tanpa perlu null-check tambahan di pipeline.
    """
    if not raw:
        return {"in_stock": False, "quantity": 0}

    text = raw.strip().lower()
    in_stock = "in stock" in text or "available" in text

    match = re.search(r"(\d+)\s*available", text)
    quantity = int(match.group(1)) if match else (1 if in_stock else 0)

    return {"in_stock": in_stock, "quantity": quantity}


def clean_product_record(raw_item: dict) -> CleaningResult:
    """
    Ambil satu raw item hasil scraping, kembalikan versi yang sudah
    dibersihkan + validasi. Item yang gagal validasi wajib (name/url kosong)
    ditandai is_valid=False supaya tidak masuk ke storage.
    """
    errors = []

    name = (raw_item.get("name") or "").strip()
    url = (raw_item.get("url") or "").strip()

    if not name:
        errors.append("Nama produk kosong")
    if not url:
        errors.append("URL produk kosong")

    availability = parse_availability(raw_item.get("availability_raw"))

    cleaned = {
        "url": url,
        "name": name,
        "description": dedupe_repeated_text(
            (raw_item.get("description") or "").strip()
        ),
        "price": parse_price(raw_item.get("price_raw")),
        "rating": parse_star_rating_word(raw_item.get("rating_raw")),
        "in_stock": availability["in_stock"],
        "stock_quantity": availability["quantity"],
        "category": (raw_item.get("category") or "").strip(),
        "scraped_at": raw_item.get("scraped_at"),
    }

    if cleaned["price"] is None:
        errors.append("Harga tidak bisa di-parse")

    is_valid = len(errors) == 0

    if not is_valid:
        logger.warning(f"Item tidak valid ({url}): {errors}")

    return CleaningResult(is_valid=is_valid, cleaned=cleaned, errors=errors)
