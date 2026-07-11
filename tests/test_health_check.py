"""
test_health_check.py
-----------------------
Unit test untuk ScraperHealthMonitor. Fokus ke dua bagian yang bisa
diuji sepenuhnya tanpa menjalankan crawl sungguhan:
  1. detect_anomalies() -- logic murni, input dict -> output list
  2. build_report() + _write_report() -- transformasi stats -> JSON file

Bagian pengiriman webhook TIDAK diuji end-to-end di sini (butuh webhook
URL sungguhan) -- lihat catatan kejujuran teknis di health_check.py.
"""

import json
from datetime import datetime, timezone

import pytest

from monitoring.health_check import ScraperHealthMonitor


def make_monitor(min_expected_items=None, report_dir="output/monitoring", webhook_url=None):
    return ScraperHealthMonitor(
        min_expected_items=min_expected_items,
        report_dir=report_dir,
        webhook_url=webhook_url,
    )


class TestAnomalyDetection:
    def test_no_anomaly_for_healthy_crawl(self):
        mon = make_monitor()
        report = {
            "requests_made": 50,
            "items_scraped": 45,
            "robots_forbidden_count": 0,
            "response_status_4xx_5xx": 0,
        }
        assert mon.detect_anomalies(report) == []

    def test_detects_zero_items_with_requests_made(self):
        mon = make_monitor()
        report = {
            "requests_made": 10,
            "items_scraped": 0,
            "robots_forbidden_count": 0,
            "response_status_4xx_5xx": 0,
        }
        anomalies = mon.detect_anomalies(report)
        assert any("ZERO_ITEMS" in a for a in anomalies)

    def test_no_zero_items_anomaly_when_no_requests_made(self):
        """Kalau memang belum ada request sama sekali (mis. spider gagal
        start), ini bukan anomali 'selector rusak' -- kasus beda."""
        mon = make_monitor()
        report = {
            "requests_made": 0,
            "items_scraped": 0,
            "robots_forbidden_count": 0,
            "response_status_4xx_5xx": 0,
        }
        anomalies = mon.detect_anomalies(report)
        assert not any("ZERO_ITEMS" in a for a in anomalies)

    def test_detects_below_threshold(self):
        mon = make_monitor(min_expected_items=100)
        report = {
            "requests_made": 50,
            "items_scraped": 30,
            "robots_forbidden_count": 0,
            "response_status_4xx_5xx": 0,
        }
        anomalies = mon.detect_anomalies(report)
        assert any("BELOW_THRESHOLD" in a for a in anomalies)

    def test_no_threshold_check_when_not_configured(self):
        mon = make_monitor(min_expected_items=None)
        report = {
            "requests_made": 50,
            "items_scraped": 1,
            "robots_forbidden_count": 0,
            "response_status_4xx_5xx": 0,
        }
        anomalies = mon.detect_anomalies(report)
        assert not any("BELOW_THRESHOLD" in a for a in anomalies)

    def test_detects_robots_blocked(self):
        mon = make_monitor()
        report = {
            "requests_made": 10,
            "items_scraped": 5,
            "robots_forbidden_count": 3,
            "response_status_4xx_5xx": 0,
        }
        anomalies = mon.detect_anomalies(report)
        assert any("ROBOTS_BLOCKED" in a for a in anomalies)

    def test_detects_high_error_rate(self):
        mon = make_monitor()
        report = {
            "requests_made": 10,
            "items_scraped": 3,
            "robots_forbidden_count": 0,
            "response_status_4xx_5xx": 6,  # 60% error rate
        }
        anomalies = mon.detect_anomalies(report)
        assert any("HIGH_ERROR_RATE" in a for a in anomalies)

    def test_low_error_rate_not_flagged(self):
        mon = make_monitor()
        report = {
            "requests_made": 100,
            "items_scraped": 90,
            "robots_forbidden_count": 0,
            "response_status_4xx_5xx": 5,  # 5% error rate
        }
        anomalies = mon.detect_anomalies(report)
        assert not any("HIGH_ERROR_RATE" in a for a in anomalies)


class TestReportGeneration:
    def test_build_report_structure(self):
        mon = make_monitor()
        mon.start_time = datetime.now(timezone.utc)

        class FakeSpider:
            name = "test_spider"

        stats = {
            "item_scraped_count": 42,
            "downloader/request_count": 50,
            "downloader/response_count": 48,
            "downloader/response_status_count/200": 45,
            "downloader/response_status_count/404": 3,
            "downloader/exception_count": 2,
        }

        report = mon.build_report(FakeSpider(), "finished", stats)

        assert report["spider_name"] == "test_spider"
        assert report["items_scraped"] == 42
        assert report["requests_made"] == 50
        assert report["response_status_2xx"] == 45
        assert report["response_status_4xx_5xx"] == 3
        assert report["exception_count"] == 2
        assert report["duration_seconds"] is not None

    def test_write_report_creates_json_file(self, tmp_path):
        mon = make_monitor(report_dir=str(tmp_path))
        report = {"spider_name": "test", "items_scraped": 5}

        mon._write_report("test_spider", report)

        files = list(tmp_path.glob("test_spider_*.json"))
        assert len(files) == 1

        with open(files[0]) as f:
            saved = json.load(f)
        assert saved["items_scraped"] == 5
