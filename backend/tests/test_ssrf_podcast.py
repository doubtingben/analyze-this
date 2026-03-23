import pytest
from unittest.mock import patch, MagicMock
from worker_podcast_derivative import _is_safe_url, _fetch_url_text
import socket

@patch('worker_podcast_derivative.socket.gethostbyname')
def test_is_safe_url(mock_gethostbyname):
    # Public IPs should be safe
    mock_gethostbyname.return_value = '8.8.8.8'
    assert _is_safe_url("http://google.com")

    mock_gethostbyname.return_value = '93.184.216.34'
    assert _is_safe_url("https://example.com/path")

    mock_gethostbyname.return_value = '8.8.8.8'
    assert _is_safe_url("http://8.8.8.8")

    # Private IPs should be unsafe
    mock_gethostbyname.return_value = '127.0.0.1'
    assert not _is_safe_url("http://localhost")
    assert not _is_safe_url("http://127.0.0.1")

    mock_gethostbyname.return_value = '169.254.169.254'
    assert not _is_safe_url("http://169.254.169.254")

    mock_gethostbyname.return_value = '192.168.1.1'
    assert not _is_safe_url("http://192.168.1.1")

    mock_gethostbyname.return_value = '10.0.0.1'
    assert not _is_safe_url("http://10.0.0.1")

    mock_gethostbyname.return_value = '0.0.0.0'
    assert not _is_safe_url("http://0.0.0.0")

    # Non-HTTP(S) schemes should be unsafe
    assert not _is_safe_url("file:///etc/passwd")
    assert not _is_safe_url("gopher://localhost:11211/")

    # Invalid URLs should be unsafe
    assert not _is_safe_url("http://")
    assert not _is_safe_url("invalid-url")

@patch('worker_podcast_derivative.socket.gethostbyname')
@patch('worker_podcast_derivative.httpx.get')
def test_fetch_url_text_safe(mock_get, mock_gethostbyname):
    mock_gethostbyname.return_value = '93.184.216.34' # example.com

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = "<p>Cleaned Text</p>"
    mock_response.headers = {"content-type": "text/html"}
    mock_get.return_value = mock_response

    result = _fetch_url_text("http://example.com")
    assert result == "Cleaned Text"
    mock_get.assert_called_once_with("http://example.com", timeout=20.0, follow_redirects=False)

@patch('worker_podcast_derivative.socket.gethostbyname')
@patch('worker_podcast_derivative.httpx.get')
def test_fetch_url_text_unsafe(mock_get, mock_gethostbyname):
    mock_gethostbyname.return_value = '169.254.169.254'

    result = _fetch_url_text("http://169.254.169.254/latest/meta-data/")
    assert result == ""
    mock_get.assert_not_called()

@patch('worker_podcast_derivative.socket.gethostbyname')
@patch('worker_podcast_derivative.httpx.get')
def test_fetch_url_text_redirect_safe_to_unsafe(mock_get, mock_gethostbyname):
    # Simulate first call returns safe IP, second call returns unsafe IP
    mock_gethostbyname.side_effect = ['93.184.216.34', '127.0.0.1']

    # Setup mock to simulate a redirect
    redirect_response = MagicMock()
    redirect_response.status_code = 301
    redirect_response.headers = {"location": "http://localhost/admin"}

    mock_get.side_effect = [redirect_response]

    result = _fetch_url_text("http://example.com/redirect")
    assert result == ""
    # Should only be called once because the next URL is unsafe
    mock_get.assert_called_once_with("http://example.com/redirect", timeout=20.0, follow_redirects=False)

@patch('worker_podcast_derivative.socket.gethostbyname')
@patch('worker_podcast_derivative.httpx.get')
def test_fetch_url_text_too_many_redirects(mock_get, mock_gethostbyname):
    mock_gethostbyname.return_value = '93.184.216.34'

    # Setup mock to simulate an infinite redirect loop
    redirect_response = MagicMock()
    redirect_response.status_code = 301
    redirect_response.headers = {"location": "http://example.com/redirect"}

    mock_get.return_value = redirect_response

    result = _fetch_url_text("http://example.com/redirect")
    assert result == ""
    # Should be called max_redirects + 1 times
    assert mock_get.call_count == 6
