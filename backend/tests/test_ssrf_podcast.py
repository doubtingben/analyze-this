import unittest
from unittest.mock import patch, MagicMock
import httpx
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_DIR not in sys.path:
    sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

from podcast_content import _extract_remote_text

class TestSSRFProtection(unittest.TestCase):
    @patch('podcast_content._resolve_and_validate_ip')
    def test_ssrf_private_ip(self, mock_resolve_ip):
        mock_resolve_ip.return_value = None
        result = _extract_remote_text('http://192.168.1.1')
        self.assertIsNone(result)

    @patch('podcast_content._resolve_and_validate_ip')
    def test_ssrf_localhost(self, mock_resolve_ip):
        mock_resolve_ip.return_value = None
        result = _extract_remote_text('http://localhost')
        self.assertIsNone(result)

    @patch('podcast_content._resolve_and_validate_ip')
    def test_ssrf_metadata_ip(self, mock_resolve_ip):
        mock_resolve_ip.return_value = None
        result = _extract_remote_text('http://169.254.169.254')
        self.assertIsNone(result)

    @patch('podcast_content._resolve_and_validate_ip')
    def test_ssrf_unspecified(self, mock_resolve_ip):
        mock_resolve_ip.return_value = None
        result = _extract_remote_text('http://0.0.0.0')
        self.assertIsNone(result)

    @patch('podcast_content._resolve_and_validate_ip')
    @patch('httpx.Client.get')
    def test_ssrf_redirect_to_private(self, mock_get, mock_resolve_ip):
        # Initial DNS resolution is safe, second is not
        mock_resolve_ip.side_effect = ['93.184.216.34', None]

        # Mock first response to be a redirect
        first_response = MagicMock()
        first_response.is_redirect = True
        first_response.status_code = 302
        first_response.headers = {'Location': 'http://localhost'}
        first_response.raise_for_status = MagicMock()

        mock_get.return_value = first_response

        result = _extract_remote_text('http://example.com')
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
