import unittest
from unittest.mock import patch, MagicMock
import httpx
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import podcast_content

class TestPodcastSSRF(unittest.TestCase):
    @patch("podcast_content.socket.gethostbyname")
    def test_ssrf_blocked(self, mock_gethostbyname):
        mock_gethostbyname.return_value = "127.0.0.1"

        text, details = podcast_content._extract_remote_text_with_diagnostics("http://localhost:8080/admin")
        self.assertIsNone(text)
        self.assertIn("ValueError", details.get("failure_reason", ""))

    @patch("podcast_content.socket.gethostbyname")
    @patch("podcast_content.httpx.Client.get")
    def test_ssrf_allowed(self, mock_get, mock_gethostbyname):
        mock_gethostbyname.return_value = "93.184.216.34" # example.com

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.is_redirect = False
        mock_resp.content = b"<html><body><p>Hello world</p></body></html>"
        mock_resp.headers = {"content-type": "text/html"}
        mock_resp.url = httpx.URL("http://example.com")
        mock_get.return_value = mock_resp

        text, details = podcast_content._extract_remote_text_with_diagnostics("http://example.com")
        self.assertEqual(text, "Hello world")
        self.assertEqual(details["status_code"], 200)

if __name__ == "__main__":
    unittest.main()
