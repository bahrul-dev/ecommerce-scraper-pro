"""
test_proxy_rotator.py
------------------------
Unit test murni untuk logic ProxyRotatorMiddleware -- tidak butuh proxy
sungguhan atau koneksi internet. Menguji: rotasi, health tracking,
cooldown, dan pass-through kalau tidak ada proxy dikonfigurasi.
"""

import time
from unittest.mock import MagicMock

import pytest

from middlewares.proxy_rotator import ProxyRotatorMiddleware


def make_request(meta=None):
    req = MagicMock()
    req.meta = meta if meta is not None else {}
    return req


def make_response(status=200):
    resp = MagicMock()
    resp.status = status
    return resp


class TestProxyRotatorPassThrough:
    def test_no_proxy_configured_means_passthrough(self):
        mw = ProxyRotatorMiddleware(proxy_list=[])
        req = make_request()
        result = mw.process_request(req, spider=None)
        assert result is None
        assert "proxy" not in req.meta


class TestProxyRotatorAssignment:
    def test_assigns_proxy_from_list(self):
        mw = ProxyRotatorMiddleware(proxy_list=["http://proxy1:8080"])
        req = make_request()
        mw.process_request(req, spider=None)
        assert req.meta["proxy"] == "http://proxy1:8080"

    def test_rotates_across_multiple_calls(self):
        proxies = ["http://p1:8080", "http://p2:8080", "http://p3:8080"]
        mw = ProxyRotatorMiddleware(proxy_list=proxies)

        seen = set()
        for _ in range(20):
            req = make_request()
            mw.process_request(req, spider=None)
            seen.add(req.meta["proxy"])

        # Dengan 20 percobaan dan pemilihan acak, harusnya semua proxy
        # kepakai minimal sekali (probabilitas gagal sangat kecil)
        assert seen == set(proxies)


class TestProxyRotatorHealthTracking:
    def test_marks_proxy_unhealthy_after_threshold_failures(self):
        mw = ProxyRotatorMiddleware(proxy_list=["http://p1:8080"])

        for _ in range(mw.FAILURE_THRESHOLD):
            req = make_request(meta={"_proxy_used": "http://p1:8080"})
            mw.process_response(req, make_response(status=429), spider=None)

        # Proxy sekarang harus dalam cooldown
        assert mw._cooldown_until["http://p1:8080"] > time.time()

    def test_healthy_response_resets_failure_count(self):
        mw = ProxyRotatorMiddleware(proxy_list=["http://p1:8080"])
        req = make_request(meta={"_proxy_used": "http://p1:8080"})

        mw.process_response(req, make_response(status=429), spider=None)
        assert mw._failure_count["http://p1:8080"] == 1

        mw.process_response(req, make_response(status=200), spider=None)
        assert mw._failure_count["http://p1:8080"] == 0

    def test_unhealthy_proxy_excluded_from_selection(self):
        mw = ProxyRotatorMiddleware(proxy_list=["http://p1:8080", "http://p2:8080"])
        mw._cooldown_until["http://p1:8080"] = time.time() + 60

        for _ in range(10):
            req = make_request()
            mw.process_request(req, spider=None)
            assert req.meta["proxy"] == "http://p2:8080"

    def test_falls_back_to_no_proxy_when_all_unhealthy(self):
        mw = ProxyRotatorMiddleware(proxy_list=["http://p1:8080"])
        mw._cooldown_until["http://p1:8080"] = time.time() + 60

        req = make_request()
        result = mw.process_request(req, spider=None)
        assert result is None
        assert "proxy" not in req.meta
