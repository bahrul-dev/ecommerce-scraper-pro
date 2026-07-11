"""
preview_cleaned_data.py
-------------------------
Utility kecil untuk melihat hasil DATA CLEANING tanpa perlu setup
PostgreSQL/MongoDB terlebih dahulu.

Alasan skrip ini ada: cleaning (dedupe deskripsi, parsing harga/rating/
stok) hanya berjalan di dalam item pipeline (postgres_pipeline.py /
mongodb_pipeline.py), yang baru aktif kalau database sungguhan
tersambung. Kalau spider dijalankan dengan ITEM_PIPELINES={} (mis. untuk
smoke test cepat tanpa database), output JSON yang dihasilkan masih
RAW -- belum melalui proses cleaning sama sekali. Skrip ini menjembatani
itu: ambil raw JSON hasil scraping, jalankan lewat fungsi cleaning yang
sama persis dipakai pipeline sungguhan, lalu tampilkan hasilnya.

Cara pakai:
    1. Jalankan scraping tanpa pipeline dulu (cepat, tanpa database):
       scrapy crawl ecommerce -s ITEM_PIPELINES={} -O output/raw.json

    2. Preview hasil setelah dibersihkan:
       python scripts/preview_cleaned_data.py output/raw.json
"""

import json
import sys
from pathlib import Path

# Supaya bisa import data_cleaning saat dijalankan dari folder scripts/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data_cleaning.cleaner import clean_product_record


def main():
    if len(sys.argv) < 2:
        print("Pemakaian: python scripts/preview_cleaned_data.py <path_ke_raw_json>")
        sys.exit(1)

    raw_path = Path(sys.argv[1])
    if not raw_path.exists():
        print(f"File tidak ditemukan: {raw_path}")
        sys.exit(1)

    with open(raw_path, encoding="utf-8") as f:
        raw_items = json.load(f)

    print(f"Memproses {len(raw_items)} item dari {raw_path}...\n")

    valid_count = 0
    invalid_count = 0
    cleaned_items = []

    for i, raw_item in enumerate(raw_items, start=1):
        result = clean_product_record(raw_item)
        cleaned_items.append(result.cleaned)

        status = "OK" if result.is_valid else "INVALID"
        if result.is_valid:
            valid_count += 1
        else:
            invalid_count += 1

        print(f"[{i}] {status} — {result.cleaned.get('name', '(tanpa nama)')}")
        print(f"    price: {result.cleaned.get('price')}")
        print(f"    rating: {result.cleaned.get('rating')}")
        print(f"    in_stock: {result.cleaned.get('in_stock')} "
              f"(qty: {result.cleaned.get('stock_quantity')})")
        desc = result.cleaned.get("description", "")
        preview = desc[:100] + ("..." if len(desc) > 100 else "")
        print(f"    description: {preview}")
        if not result.is_valid:
            print(f"    errors: {result.errors}")
        print()

    print(f"--- Ringkasan: {valid_count} valid, {invalid_count} invalid ---")

    output_path = raw_path.parent / f"cleaned_{raw_path.name}"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(cleaned_items, f, indent=2, ensure_ascii=False)
    print(f"Hasil lengkap yang sudah dibersihkan disimpan ke: {output_path}")


if __name__ == "__main__":
    main()
