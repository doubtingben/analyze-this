import unittest
from unittest.mock import patch
import ipaddress
import socket

from worker_podcast_derivative import _is_safe_url, _fetch_url_text

class TestPodcastSSRF(unittest.TestCase):
    @patch('socket.gethostbyname')
    def test_safe_urls(self, mock_gethostbyname):
        mock_gethostbyname.return_value = "8.8.8.8"
        self.assertTrue(_is_safe_url("http://example.com"))
        self.assertTrue(_is_safe_url("https://example.com/path"))

    @patch('socket.gethostbyname')
    def test_blocked_urls(self, mock_gethostbyname):
        # Localhost
        mock_gethostbyname.return_value = "127.0.0.1"
        self.assertFalse(_is_safe_url("http://localhost"))

        # Private IP
        mock_gethostbyname.return_value = "192.168.1.5"
        self.assertFalse(_is_safe_url("http://internal.service"))

        # Link-local / AWS metadata
        mock_gethostbyname.return_value = "169.254.169.254"
        self.assertFalse(_is_safe_url("http://169.254.169.254/latest/meta-data/"))

        # Unspecified
        mock_gethostbyname.return_value = "0.0.0.0"
        self.assertFalse(_is_safe_url("http://0.0.0.0/"))

    def test_invalid_scheme(self):
        self.assertFalse(_is_safe_url("file:///etc/passwd"))
        self.assertFalse(_is_safe_url("ftp://example.com"))

if __name__ == '__main__':
    unittest.main()
