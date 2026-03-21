import pytest
from httpx import Response
from unittest.mock import patch, MagicMock
from worker_podcast_derivative import _fetch_url_text, _is_safe_url

def test_is_safe_url_blocks_private():
    assert _is_safe_url("http://169.254.169.254/metadata") is False
    assert _is_safe_url("http://127.0.0.1:8080/") is False
    assert _is_safe_url("http://localhost/") is False
    assert _is_safe_url("http://192.168.1.1/") is False
    assert _is_safe_url("http://10.0.0.1/") is False
    assert _is_safe_url("file:///etc/passwd") is False

@patch("worker_podcast_derivative.socket.gethostbyname")
def test_is_safe_url_allows_public(mock_gethostbyname):
    # Mock DNS resolution for a public IP
    mock_gethostbyname.return_value = "8.8.8.8"
    assert _is_safe_url("https://example.com/article") is True
    assert _is_safe_url("http://google.com/") is True


@patch("worker_podcast_derivative.httpx.get")
@patch("worker_podcast_derivative.socket.gethostbyname")
def test_fetch_url_text_ssrf_mitigation(mock_gethostbyname, mock_get):
    mock_get.return_value = Response(200, text="Internal metadata", request=MagicMock())

    # 1. Test that unsafe URL returns empty string and doesn't call get()
    result = _fetch_url_text("http://169.254.169.254/metadata")
    assert result == ""
    mock_get.assert_not_called()

    # 2. Test that safe URL returns content and calls get()
    mock_gethostbyname.return_value = "8.8.8.8"
    result = _fetch_url_text("https://example.com/article")
    assert result == "Internal metadata"
    mock_get.assert_called_once()

@patch("worker_podcast_derivative.httpx.get")
@patch("worker_podcast_derivative.socket.gethostbyname")
def test_fetch_url_text_redirect_ssrf(mock_gethostbyname, mock_get):
    # Setup DNS to always return a safe IP, to test only the redirect mitigation part
    mock_gethostbyname.return_value = "8.8.8.8"

    # Initial request returns a redirect to a local IP
    redirect_response = Response(
        302,
        headers={"Location": "http://169.254.169.254/metadata"},
        request=MagicMock()
    )

    # If the second request gets made, we want to know, but _fetch_url_text should block it
    mock_get.side_effect = [redirect_response]

    # Note: socket.gethostbyname is still patched, but we pass "http://169.254.169.254/" in redirect
    # The _is_safe_url parses this and uses ipaddress.ip_address on 169.254.169.254 (if the host is already an IP, it often parses fine or gethostbyname returns it)
    # Actually, we should make sure gethostbyname returns the private IP if given the private IP string
    def mock_dns(hostname):
        if hostname == "169.254.169.254": return "169.254.169.254"
        return "8.8.8.8"
    mock_gethostbyname.side_effect = mock_dns

    result = _fetch_url_text("https://example.com/article")

    # The function should see the redirect, validate the new URL, block it, and return ""
    assert result == ""
    # Should only be called once (for the initial example.com request)
    assert mock_get.call_count == 1
