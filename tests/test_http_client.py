import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.http_client import fetch


@pytest.fixture(autouse=True)
def reset_rate_limit():
    """Reset rate limiting state before each test."""
    import src.http_client
    src.http_client._last_request_time = None
    yield


def test_fetch_success():
    """Test successful fetch."""
    with patch("src.http_client.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>test</html>"
        mock_get.return_value = mock_response

        result = fetch("https://example.com")

        assert result == "<html>test</html>"
        mock_get.assert_called_once()
        assert mock_get.call_args[1]["headers"]["User-Agent"].startswith("itch-creators-scraper")


def test_fetch_rate_limiting():
    """Test that rate limiting enforces minimum delay."""
    with patch("src.http_client.httpx.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>test</html>"
        mock_get.return_value = mock_response

        start = time.time()

        # First request
        fetch("https://example.com/1")

        # Second request should be delayed
        fetch("https://example.com/2")

        elapsed = time.time() - start

        # Should have waited at least 1 second between requests
        assert elapsed >= 1.0
        assert mock_get.call_count == 2


def test_fetch_429_retry():
    """Test retry logic on rate limiting (429)."""
    with patch("src.http_client.httpx.get") as mock_get, \
         patch("src.http_client.time.sleep") as mock_sleep, \
         patch("src.http_client.random.uniform", return_value=0.0):

        # First attempt returns 429, second succeeds
        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = "<html>success</html>"

        mock_get.side_effect = [mock_response_429, mock_response_200]

        result = fetch("https://example.com")

        assert result == "<html>success</html>"
        assert mock_get.call_count == 2
        # Should have slept for exponential backoff
        mock_sleep.assert_called()


def test_fetch_500_retry():
    """Test retry logic on server error (500)."""
    with patch("src.http_client.httpx.get") as mock_get, \
         patch("src.http_client.time.sleep") as mock_sleep, \
         patch("src.http_client.random.uniform", return_value=0.0):

        # First attempt returns 500, second succeeds
        mock_response_500 = MagicMock()
        mock_response_500.status_code = 500

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = "<html>success</html>"

        mock_get.side_effect = [mock_response_500, mock_response_200]

        result = fetch("https://example.com")

        assert result == "<html>success</html>"
        assert mock_get.call_count == 2
        mock_sleep.assert_called()


def test_fetch_max_retries_exceeded():
    """Test that fetch fails after max retries."""
    with patch("src.http_client.httpx.get") as mock_get, \
         patch("src.http_client.time.sleep"), \
         patch("src.http_client.random.uniform", return_value=0.0):

        # All attempts return 429
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPError):
            fetch("https://example.com", max_retries=3)

        # Should have tried 3 times
        assert mock_get.call_count == 3


def test_fetch_timeout_retry():
    """Test retry on timeout."""
    with patch("src.http_client.httpx.get") as mock_get, \
         patch("src.http_client.time.sleep"), \
         patch("src.http_client.random.uniform", return_value=0.0):

        # First attempt times out, second succeeds
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "<html>success</html>"

        mock_get.side_effect = [httpx.TimeoutException("Timeout"), mock_response]

        result = fetch("https://example.com")

        assert result == "<html>success</html>"
        assert mock_get.call_count == 2


def test_fetch_non_retryable_error():
    """Test that non-retryable errors (404, etc.) don't retry."""
    with patch("src.http_client.httpx.get") as mock_get:

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not found", request=MagicMock(), response=mock_response
        )
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPStatusError):
            fetch("https://example.com")

        # Should only try once (no retry)
        assert mock_get.call_count == 1


def test_exponential_backoff():
    """Test that exponential backoff increases correctly."""
    with patch("src.http_client.httpx.get") as mock_get, \
         patch("src.http_client.time.sleep") as mock_sleep, \
         patch("src.http_client.random.uniform", return_value=0.0):

        # All attempts return 429
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        with pytest.raises(httpx.HTTPError):
            fetch("https://example.com", max_retries=3)

        # Check that sleep was called with increasing durations
        sleep_calls = [call[0][0] for call in mock_sleep.call_args_list]
        assert len(sleep_calls) >= 2
        # First backoff should be at least 2s, second at least 4s
        assert sleep_calls[0] >= 2  # 2^0 * 2
        assert sleep_calls[1] >= 4  # 2^1 * 2


def test_retry_after_respected():
    """Test that Retry-After header increases backoff."""
    with patch("src.http_client.httpx.get") as mock_get, \
         patch("src.http_client.time.sleep") as mock_sleep, \
         patch("src.http_client.random.uniform", return_value=0.0):

        mock_response_429 = MagicMock()
        mock_response_429.status_code = 429
        mock_response_429.headers = {"Retry-After": "10"}

        mock_response_200 = MagicMock()
        mock_response_200.status_code = 200
        mock_response_200.text = "<html>success</html>"

        mock_get.side_effect = [mock_response_429, mock_response_200]

        result = fetch("https://example.com")

        assert result == "<html>success</html>"
        assert mock_sleep.call_args_list[0][0][0] >= 10
