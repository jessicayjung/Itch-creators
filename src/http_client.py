import random
import time
from typing import Optional

import httpx


# Track last request time for rate limiting
_last_request_time: Optional[float] = None
_min_delay_seconds = 1.0
_user_agent = "itch-creators-scraper/1.0 (Educational project for ranking game creators)"


def fetch(url: str, max_retries: int = 3) -> str:
    """
    Fetch HTML from a URL with rate limiting and retries.

    Args:
        url: The URL to fetch
        max_retries: Maximum number of retry attempts

    Returns:
        Raw HTML string

    Raises:
        httpx.HTTPError: If request fails after all retries
    """
    global _last_request_time

    # Enforce rate limiting
    if _last_request_time is not None:
        elapsed = time.time() - _last_request_time
        if elapsed < _min_delay_seconds:
            time.sleep(_min_delay_seconds - elapsed)

    headers = {"User-Agent": _user_agent}

    for attempt in range(max_retries):
        try:
            _last_request_time = time.time()

            response = httpx.get(url, headers=headers, timeout=30.0, follow_redirects=True)

            # Success
            if response.status_code == 200:
                return response.text

            # Rate limited - exponential backoff
            if response.status_code == 429:
                wait_time = _get_backoff_time(response, attempt)
                time.sleep(wait_time)
                continue

            # Server error - retry with backoff
            if 500 <= response.status_code < 600:
                wait_time = _get_backoff_time(response, attempt)
                time.sleep(wait_time)
                continue

            # Other errors - don't retry, raise immediately
            response.raise_for_status()

        except httpx.HTTPStatusError:
            # Client errors (4xx) - don't retry
            raise

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                wait_time = _get_backoff_time(None, attempt)
                time.sleep(wait_time)
                continue
            raise

        except httpx.HTTPError as e:
            if attempt < max_retries - 1:
                wait_time = _get_backoff_time(None, attempt)
                time.sleep(wait_time)
                continue
            raise

    # If we get here, all retries failed
    raise httpx.HTTPError(f"Failed to fetch {url} after {max_retries} attempts")


def _get_backoff_time(response: httpx.Response | None, attempt: int) -> float:
    """Calculate backoff time with optional Retry-After and jitter."""
    base_wait = (2 ** attempt) * 2
    retry_after = _parse_retry_after(response) if response else None
    wait_time = max(base_wait, retry_after) if retry_after is not None else base_wait
    jitter = random.uniform(0.0, 1.0)
    return wait_time + jitter


def _parse_retry_after(response: httpx.Response | None) -> int | None:
    """Parse Retry-After header if present (seconds)."""
    if response is None:
        return None
    header = response.headers.get("Retry-After")
    if not header or not isinstance(header, str):
        return None
    try:
        return int(header)
    except ValueError:
        return None
