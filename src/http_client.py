import time
from typing import Optional

import httpx


# Track last request time for rate limiting
_last_request_time: Optional[float] = None
_min_delay_seconds = 2.0
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
                wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                time.sleep(wait_time)
                continue

            # Server error - retry with backoff
            if 500 <= response.status_code < 600:
                wait_time = (2 ** attempt) * 2
                time.sleep(wait_time)
                continue

            # Other errors - don't retry, raise immediately
            response.raise_for_status()

        except httpx.HTTPStatusError:
            # Client errors (4xx) - don't retry
            raise

        except httpx.TimeoutException:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                time.sleep(wait_time)
                continue
            raise

        except httpx.HTTPError as e:
            if attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 2
                time.sleep(wait_time)
                continue
            raise

    # If we get here, all retries failed
    raise httpx.HTTPError(f"Failed to fetch {url} after {max_retries} attempts")
