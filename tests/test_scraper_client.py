"""Unit tests for winb.scraper.client.

These tests do NOT hit the network; they exercise URL normalization,
cache key stability, cache read/write, and rate-limit timing.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from winb.scraper.client import BleagueClient, FetchResult


# --- URL normalization ------------------------------------------------------


class TestNormalizeUrl:
    def test_drops_fragment(self):
        url = "https://example.com/path?a=1#section"
        assert BleagueClient.normalize_url(url) == "https://example.com/path?a=1"

    def test_sorts_query_params(self):
        url1 = "https://example.com/?b=2&a=1&c=3"
        url2 = "https://example.com/?c=3&a=1&b=2"
        assert BleagueClient.normalize_url(url1) == BleagueClient.normalize_url(url2)

    def test_preserves_path_and_scheme(self):
        url = "https://www.bleague.jp/game_detail/?ScheduleKey=505443&tab=1"
        out = BleagueClient.normalize_url(url)
        assert out.startswith("https://www.bleague.jp/game_detail/")
        assert "ScheduleKey=505443" in out
        assert "tab=1" in out

    def test_empty_query_ok(self):
        url = "https://www.bleague.jp/"
        assert BleagueClient.normalize_url(url) == "https://www.bleague.jp/"


# --- Cache key stability ---------------------------------------------------


class TestCacheKey:
    def test_same_url_same_key(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        url = "https://example.com/?a=1&b=2"
        k1 = client._cache_key(url)
        k2 = client._cache_key(url)
        assert k1 == k2

    def test_different_query_order_same_key(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        k1 = client._cache_key("https://example.com/?a=1&b=2")
        k2 = client._cache_key("https://example.com/?b=2&a=1")
        assert k1 == k2

    def test_fragment_ignored(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        k1 = client._cache_key("https://example.com/path?a=1")
        k2 = client._cache_key("https://example.com/path?a=1#frag")
        assert k1 == k2


# --- Cache read/write ------------------------------------------------------


class TestCacheIO:
    def test_roundtrip(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        url = "https://example.com/sample"
        html = "<html><body>Hello</body></html>"

        # No cache initially
        assert client._read_cache(url) is None

        # Write & read back
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        client._write_cache(url, html, 200, now)

        cached = client._read_cache(url)
        assert cached is not None
        assert cached.html == html
        assert cached.status_code == 200
        assert cached.from_cache is True
        assert cached.url == url

    def test_corrupted_cache_meta_returns_none(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        url = "https://example.com/sample"
        html_path, meta_path = client._cache_paths(url)
        html_path.write_text("content")
        meta_path.write_text("not valid json{{{")
        assert client._read_cache(url) is None

    def test_clear_cache(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        from datetime import datetime, timezone
        for i in range(3):
            client._write_cache(
                f"https://example.com/{i}",
                f"<p>{i}</p>",
                200,
                datetime.now(timezone.utc),
            )
        # 3 URLs × 2 files each = 6
        assert client.clear_cache() == 6


# --- Rate limiting ---------------------------------------------------------


class TestRateLimit:
    def test_no_wait_on_first_call(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=10)
        start = time.monotonic()
        client._wait_for_rate_limit()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # essentially no wait

    def test_sleeps_when_interval_not_met(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0.5)
        client._last_request_at = time.monotonic()  # just now
        start = time.monotonic()
        client._wait_for_rate_limit()
        elapsed = time.monotonic() - start
        # Should have slept ~0.5s (allow slack for CI)
        assert 0.3 < elapsed < 1.0

    def test_no_sleep_when_interval_already_passed(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0.01)
        client._last_request_at = time.monotonic() - 1.0  # 1s ago
        start = time.monotonic()
        client._wait_for_rate_limit()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1


# --- GET with mocked network ----------------------------------------------


class TestGet:
    def test_returns_cached_on_hit(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        url = "https://example.com/a"
        from datetime import datetime, timezone
        client._write_cache(url, "<p>cached</p>", 200, datetime.now(timezone.utc))

        with patch.object(client, "_do_get") as mock_fetch:
            result = client.get(url)
            mock_fetch.assert_not_called()
            assert result.from_cache is True
            assert result.html == "<p>cached</p>"

    def test_fetches_on_miss(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = "<p>fresh</p>"

        with patch.object(client, "_do_get", return_value=mock_resp):
            result = client.get("https://example.com/b")
            assert result.from_cache is False
            assert result.html == "<p>fresh</p>"
            assert result.status_code == 200

        # Cache should now be populated
        cached = client._read_cache("https://example.com/b")
        assert cached is not None
        assert cached.html == "<p>fresh</p>"

    def test_use_cache_false_forces_fetch(self, tmp_path: Path):
        client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
        url = "https://example.com/c"
        from datetime import datetime, timezone
        client._write_cache(url, "<p>old</p>", 200, datetime.now(timezone.utc))

        mock_resp = MagicMock(spec=requests.Response)
        mock_resp.status_code = 200
        mock_resp.text = "<p>new</p>"

        with patch.object(client, "_do_get", return_value=mock_resp) as mock_fetch:
            result = client.get(url, use_cache=False)
            mock_fetch.assert_called_once()
            assert result.from_cache is False
            assert result.html == "<p>new</p>"


# --- FetchResult dataclass -------------------------------------------------


class TestFetchResult:
    def test_size_bytes(self):
        from datetime import datetime, timezone
        r = FetchResult(
            url="x",
            html="あいう",  # 3 chars × 3 bytes (UTF-8) = 9 bytes
            fetched_at=datetime.now(timezone.utc),
            status_code=200,
            from_cache=False,
        )
        assert r.size_bytes == 9


# --- Integration test (skipped by default; hits live site) -----------------


@pytest.mark.integration
@pytest.mark.skip(reason="Integration test: hits live bleague.jp. Run manually.")
def test_integration_robots_txt(tmp_path: Path):
    """Verify a real fetch works. Not run in normal test runs."""
    client = BleagueClient(cache_dir=tmp_path, min_interval_sec=0)
    result = client.get("https://www.bleague.jp/robots.txt")
    assert result.status_code == 200
    assert "User-agent" in result.html
