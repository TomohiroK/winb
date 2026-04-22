"""HTTP client for scraping B.LEAGUE official site.

Provides a rate-limited, cached HTTP GET client with retry support.

Design principles:
- Be a good citizen: enforce minimum interval between requests (default 10s),
  send a descriptive User-Agent, cache aggressively.
- Fail loud on errors except transient network issues (retry those).
- All cache artifacts are stored under ``data/cache/`` and are ignored by Git.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

import requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


# --- Defaults (can be overridden via env or constructor) -------------------

DEFAULT_TIMEOUT_SEC: float = 30.0
DEFAULT_MIN_INTERVAL_SEC: float = 10.0
DEFAULT_USER_AGENT: str = "WinB-ResearchBot/0.1 (personal research)"
DEFAULT_CACHE_DIR: Path = Path("/app/data/cache")
MAX_RETRIES: int = 3


# --- Response container -----------------------------------------------------


@dataclass
class FetchResult:
    """Result of a fetch operation, regardless of cache origin."""

    url: str
    html: str
    fetched_at: datetime
    status_code: int
    from_cache: bool

    @property
    def size_bytes(self) -> int:
        return len(self.html.encode("utf-8"))


# --- Client ----------------------------------------------------------------


class BleagueClient:
    """Rate-limited HTTP client with local HTML cache.

    Example:
        >>> client = BleagueClient()
        >>> result = client.get("https://www.bleague.jp/robots.txt")
        >>> print(result.status_code, result.from_cache)
    """

    def __init__(
        self,
        user_agent: str | None = None,
        min_interval_sec: float | None = None,
        cache_dir: Path | str | None = None,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    ) -> None:
        self.user_agent = user_agent or os.environ.get(
            "SCRAPER_USER_AGENT", DEFAULT_USER_AGENT
        )

        if min_interval_sec is None:
            env_interval = os.environ.get("SCRAPER_MIN_INTERVAL_SEC")
            min_interval_sec = (
                float(env_interval) if env_interval else DEFAULT_MIN_INTERVAL_SEC
            )
        self.min_interval_sec = float(min_interval_sec)

        self.cache_dir = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.timeout_sec = float(timeout_sec)

        # monotonic clock baseline; 0.0 means "no previous request"
        self._last_request_at: float = 0.0

        self._session = requests.Session()
        self._session.headers.update({"User-Agent": self.user_agent})

    # -- URL normalization & cache paths ------------------------------------

    @staticmethod
    def normalize_url(url: str) -> str:
        """Drop fragment and sort query parameters for cache key stability."""
        parsed = urlparse(url)
        sorted_query = sorted(parse_qsl(parsed.query, keep_blank_values=True))
        normalized_query = urlencode(sorted_query)
        return urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                normalized_query,
                "",  # drop fragment
            )
        )

    def _cache_key(self, url: str) -> str:
        normalized = self.normalize_url(url)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        key = self._cache_key(url)
        return (
            self.cache_dir / f"{key}.html",
            self.cache_dir / f"{key}.meta.json",
        )

    # -- Cache read/write ---------------------------------------------------

    def _read_cache(self, url: str) -> FetchResult | None:
        html_path, meta_path = self._cache_paths(url)
        if not html_path.exists() or not meta_path.exists():
            return None
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            html = html_path.read_text(encoding="utf-8")
            return FetchResult(
                url=meta["url"],
                html=html,
                fetched_at=datetime.fromisoformat(meta["fetched_at"]),
                status_code=int(meta["status_code"]),
                from_cache=True,
            )
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(
                "Cache read failed for %s: %s (will refetch)", url, e
            )
            return None

    def _write_cache(
        self,
        url: str,
        html: str,
        status_code: int,
        fetched_at: datetime,
    ) -> None:
        html_path, meta_path = self._cache_paths(url)
        try:
            html_path.write_text(html, encoding="utf-8")
            meta_path.write_text(
                json.dumps(
                    {
                        "url": url,
                        "fetched_at": fetched_at.isoformat(),
                        "status_code": status_code,
                        "size_bytes": len(html.encode("utf-8")),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError as e:
            # Cache write failures should not kill the fetch; just warn.
            logger.error("Cache write failed for %s: %s", url, e)

    # -- Rate limit ---------------------------------------------------------

    def _wait_for_rate_limit(self) -> None:
        """Sleep long enough that min_interval_sec has elapsed since last request."""
        if self._last_request_at <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        wait = self.min_interval_sec - elapsed
        if wait > 0:
            logger.debug("Rate-limit wait: %.2fs before next request", wait)
            time.sleep(wait)

    # -- Actual HTTP fetch with retries -------------------------------------

    @retry(
        stop=stop_after_attempt(MAX_RETRIES),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type(
            (
                requests.ConnectionError,
                requests.Timeout,
                requests.HTTPError,
            )
        ),
        reraise=True,
    )
    def _do_get(self, url: str) -> requests.Response:
        self._wait_for_rate_limit()
        self._last_request_at = time.monotonic()

        logger.info("GET %s", url)
        resp = self._session.get(url, timeout=self.timeout_sec)

        # Retry only 5xx; 4xx should fail fast and be caller's problem.
        if 500 <= resp.status_code < 600:
            resp.raise_for_status()
        if 400 <= resp.status_code < 500:
            # Non-retryable client error; raise immediately without retry.
            raise requests.HTTPError(
                f"{resp.status_code} Client Error for url: {url}",
                response=resp,
            )

        return resp

    # -- Public API ---------------------------------------------------------

    def get(self, url: str, use_cache: bool = True) -> FetchResult:
        """Fetch URL with optional caching.

        Args:
            url: Absolute URL to fetch.
            use_cache: When True, a cached copy is returned if present. When
                False, always hit the network (and overwrite cache on success).

        Returns:
            FetchResult with HTML body, fetched timestamp, status, and cache flag.

        Raises:
            requests.HTTPError: For non-retryable 4xx responses.
            requests.RequestException: For exhausted retries on 5xx/network errors.
        """
        if use_cache:
            cached = self._read_cache(url)
            if cached is not None:
                logger.info("Cache hit: %s", url)
                return cached

        resp = self._do_get(url)
        now = datetime.now(timezone.utc)
        self._write_cache(url, resp.text, resp.status_code, now)
        return FetchResult(
            url=url,
            html=resp.text,
            fetched_at=now,
            status_code=resp.status_code,
            from_cache=False,
        )

    def clear_cache(self) -> int:
        """Delete every cached file under ``cache_dir``.

        Returns:
            Number of files removed.
        """
        count = 0
        for file in self.cache_dir.glob("*"):
            if file.is_file():
                file.unlink()
                count += 1
        return count

    def close(self) -> None:
        """Close the underlying requests session."""
        self._session.close()

    # -- Context manager ----------------------------------------------------

    def __enter__(self) -> BleagueClient:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
