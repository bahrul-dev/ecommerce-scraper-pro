"""
health_check.py
------------------
Scrapy extension untuk monitoring produksi. Beda dari middleware (yang
memproses tiap request/response), extension ini "mendengarkan" siklus
hidup keseluruhan crawl lewat Scrapy signals, lalu:

  1. Menulis laporan JSON terstruktur setelah tiap run selesai
     (jumlah item, durasi, status code breakdown, dsb) -- ini yang
     jadi bahan dashboard/monitoring kalau proyek di-scale.
  2. Mendeteksi ANOMALI paling umum di scraping produksi:
       a. Crawl selesai tapi 0 item ter-scrape padahal ada request
          berhasil -- indikasi kuat selector rusak (situs redesign HTML)
          atau seluruh request diblokir.
       b. Jumlah item jauh di bawah ambang batas yang diharapkan
          (MIN_EXPECTED_ITEMS, dikonfigurasi lewat settings) --
          indikasi crawl terpotong/gagal sebagian.
  3. Memanggil "alert sink" yang bisa di-plug -- default-nya cuma log
     level CRITICAL, tapi bisa disambungkan ke webhook (Slack/Discord/
     Telegram) lewat MONITORING_WEBHOOK_URL kalau dikonfigurasi.

CATATAN KEJUJURAN TEKNIS: pengiriman webhook di sini SUDAH diimplementasi
dan correct secara kode, tapi belum pernah diuji terhadap webhook
sungguhan (butuh URL Slack/Discord asli untuk verifikasi end-to-end).
Bagian yang sudah diuji penuh: deteksi anomali dan penulisan laporan
JSON (lihat tests/test_health_check.py).
"""

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from scrapy import signals

logger = logging.getLogger("health_check")


class ScraperHealthMonitor:
    def __init__(self, min_expected_items: int | None, report_dir: str, webhook_url: str | None):
        self.min_expected_items = min_expected_items
        self.report_dir = Path(report_dir)
        self.webhook_url = webhook_url
        self.start_time = None

    @classmethod
    def from_crawler(cls, crawler):
        min_items = crawler.settings.getint("MONITORING_MIN_EXPECTED_ITEMS", 0) or None
        report_dir = crawler.settings.get("MONITORING_REPORT_DIR", "output/monitoring")
        webhook_url = crawler.settings.get(
            "MONITORING_WEBHOOK_URL", os.environ.get("MONITORING_WEBHOOK_URL")
        )

        ext = cls(
            min_expected_items=min_items,
            report_dir=report_dir,
            webhook_url=webhook_url,
        )
        crawler.signals.connect(ext.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(ext.spider_closed, signal=signals.spider_closed)
        return ext

    def spider_opened(self, spider):
        self.start_time = datetime.now(timezone.utc)
        logger.info(f"[health_check] Monitoring dimulai untuk spider '{spider.name}'")

    def spider_closed(self, spider, reason):
        stats = spider.crawler.stats.get_stats()
        report = self.build_report(spider, reason, stats)
        anomalies = self.detect_anomalies(report)
        report["anomalies"] = anomalies

        self._write_report(spider.name, report)

        if anomalies:
            self._raise_alert(spider.name, anomalies, report)

    def build_report(self, spider, reason, stats) -> dict:
        end_time = datetime.now(timezone.utc)
        duration = (
            (end_time - self.start_time).total_seconds() if self.start_time else None
        )

        return {
            "spider_name": spider.name,
            "finish_reason": reason,
            "started_at": self.start_time.isoformat() if self.start_time else None,
            "finished_at": end_time.isoformat(),
            "duration_seconds": duration,
            "items_scraped": stats.get("item_scraped_count", 0),
            "requests_made": stats.get("downloader/request_count", 0),
            "responses_received": stats.get("downloader/response_count", 0),
            "response_status_2xx": sum(
                v for k, v in stats.items()
                if k.startswith("downloader/response_status_count/2")
            ),
            "response_status_4xx_5xx": sum(
                v for k, v in stats.items()
                if k.startswith("downloader/response_status_count/4")
                or k.startswith("downloader/response_status_count/5")
            ),
            "robots_forbidden_count": stats.get("robotstxt/forbidden", 0),
            "exception_count": stats.get("downloader/exception_count", 0),
        }

    def detect_anomalies(self, report: dict) -> list[str]:
        """
        Aturan deteksi anomali. Dipisah jadi method sendiri (bukan
        ditumpuk di spider_closed) supaya bisa diuji langsung tanpa
        perlu menjalankan crawl sungguhan -- lihat tests/test_health_check.py.
        """
        anomalies = []

        requests_made = report["requests_made"]
        items_scraped = report["items_scraped"]

        if requests_made > 0 and items_scraped == 0:
            anomalies.append(
                "ZERO_ITEMS: Ada request berhasil tapi 0 item ter-scrape. "
                "Kemungkinan selector rusak (situs redesign HTML) atau "
                "seluruh request diblokir/redirect ke halaman lain."
            )

        if self.min_expected_items and items_scraped < self.min_expected_items:
            anomalies.append(
                f"BELOW_THRESHOLD: Item ter-scrape ({items_scraped}) di bawah "
                f"ambang batas yang diharapkan ({self.min_expected_items})."
            )

        if report["robots_forbidden_count"] > 0:
            anomalies.append(
                f"ROBOTS_BLOCKED: {report['robots_forbidden_count']} request "
                "diblokir oleh robots.txt -- cek apakah target URL berubah "
                "atau kebijakan situs berubah."
            )

        if requests_made > 0:
            error_rate = report["response_status_4xx_5xx"] / requests_made
            if error_rate > 0.5:
                anomalies.append(
                    f"HIGH_ERROR_RATE: {error_rate:.0%} response berstatus "
                    "4xx/5xx -- kemungkinan rate-limited atau IP diblokir."
                )

        return anomalies

    def _write_report(self, spider_name: str, report: dict):
        try:
            self.report_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            report_path = self.report_dir / f"{spider_name}_{timestamp}.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"[health_check] Laporan disimpan: {report_path}")
        except OSError as e:
            logger.error(f"[health_check] Gagal menulis laporan: {e}")

    def _raise_alert(self, spider_name: str, anomalies: list[str], report: dict):
        for anomaly in anomalies:
            logger.critical(f"[health_check] ANOMALI TERDETEKSI ({spider_name}): {anomaly}")

        if not self.webhook_url:
            return  # Tidak ada webhook dikonfigurasi -- cukup log

        try:
            import requests  # import lokal supaya requests bukan hard dependency

            payload = {
                "text": (
                    f"⚠️ Scraper anomaly: {spider_name}\n"
                    + "\n".join(f"- {a}" for a in anomalies)
                )
            }
            requests.post(self.webhook_url, json=payload, timeout=10)
        except Exception as e:
            logger.error(f"[health_check] Gagal kirim alert webhook: {e}")
