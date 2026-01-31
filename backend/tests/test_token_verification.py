import unittest
import os
import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

# Add backend directory to path
BACKEND_DIR = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.append(BACKEND_DIR)
os.chdir(BACKEND_DIR)

# Mock Environment BEFORE importing main
os.environ["APP_ENV"] = "production"
os.environ["GOOGLE_CLIENT_ID"] = "valid-client-id"
os.environ["GOOGLE_EXTENSION_CLIENT_ID"] = "valid-extension-id"

import main

class TestTokenVerification(unittest.TestCase):
    def setUp(self):
        main.GOOGLE_CLIENT_ID = "valid-client-id"
        main.GOOGLE_EXTENSION_CLIENT_ID = "valid-extension-id"
        main.GOOGLE_IOS_CLIENT_ID = "valid-ios-id"
        main.GOOGLE_ANDROID_CLIENT_ID = "valid-android-id"
        main.APP_ENV = "production"

    @patch('main.run_in_threadpool')
    @patch('httpx.AsyncClient')
    def test_verify_access_token_confused_deputy(self, mock_httpx_client, mock_run_in_threadpool):
        """
        Test that an access token issued to a DIFFERENT app is rejected (Confused Deputy Attack).
        """
        # Mock ID token verification failing (Method 1)
        mock_run_in_threadpool.side_effect = ValueError("Invalid ID Token")

        # Mock Method 2 (Access Token)
        token = "token-from-evil-app"

        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_get = AsyncMock()
        mock_client_instance.get = mock_get

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "email": "victim@example.com",
            "name": "Victim",
            "picture": "http://pic.com"
        }

        tokeninfo_response = MagicMock()
        tokeninfo_response.status_code = 200
        # Evil audience
        tokeninfo_response.json.return_value = {
            "aud": "evil-client-id",
            "scope": "email"
        }

        async def get_side_effect(url, headers=None, params=None):
            if "tokeninfo" in url:
                return tokeninfo_response
            if "userinfo" in url:
                return userinfo_response
            return MagicMock(status_code=404)

        mock_get.side_effect = get_side_effect

        # Run the function
        result = asyncio.run(main.verify_google_token(token))

        # Expectation: Security fix should block this
        self.assertIsNone(result, "Should reject token with invalid audience")

    @patch('main.run_in_threadpool')
    @patch('httpx.AsyncClient')
    def test_verify_access_token_valid(self, mock_httpx_client, mock_run_in_threadpool):
        """
        Test that an access token issued to OUR app is accepted.
        """
        mock_run_in_threadpool.side_effect = ValueError("Invalid ID Token")
        token = "valid-token"

        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_get = AsyncMock()
        mock_client_instance.get = mock_get

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "email": "user@example.com",
            "name": "User",
            "picture": "http://pic.com"
        }

        tokeninfo_response = MagicMock()
        tokeninfo_response.status_code = 200
        # Valid audience
        tokeninfo_response.json.return_value = {
            "aud": "valid-client-id",
            "scope": "email"
        }

        async def get_side_effect(url, headers=None, params=None):
            if "tokeninfo" in url:
                return tokeninfo_response
            if "userinfo" in url:
                return userinfo_response
            return MagicMock(status_code=404)

        mock_get.side_effect = get_side_effect

        result = asyncio.run(main.verify_google_token(token))

        self.assertIsNotNone(result)
        self.assertEqual(result['email'], "user@example.com")

    @patch('main.run_in_threadpool')
    @patch('httpx.AsyncClient')
    def test_verify_access_token_ios(self, mock_httpx_client, mock_run_in_threadpool):
        """
        Test that an access token issued to the iOS app is accepted.
        """
        mock_run_in_threadpool.side_effect = ValueError("Invalid ID Token")
        token = "ios-token"

        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_get = AsyncMock()
        mock_client_instance.get = mock_get

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "email": "ios-user@example.com",
            "name": "iOS User",
            "picture": "http://pic.com/ios"
        }

        tokeninfo_response = MagicMock()
        tokeninfo_response.status_code = 200
        # Valid IOS audience
        tokeninfo_response.json.return_value = {
            "aud": "valid-ios-id",
            "scope": "email"
        }

        async def get_side_effect(url, headers=None, params=None):
            if "tokeninfo" in url:
                return tokeninfo_response
            if "userinfo" in url:
                return userinfo_response
            return MagicMock(status_code=404)

        mock_get.side_effect = get_side_effect

        result = asyncio.run(main.verify_google_token(token))

        self.assertIsNotNone(result)
        self.assertEqual(result['email'], "ios-user@example.com")

    @patch('main.run_in_threadpool')
    @patch('httpx.AsyncClient')
    def test_verify_access_token_android(self, mock_httpx_client, mock_run_in_threadpool):
        """
        Test that an access token issued to the Android app is accepted.
        """
        mock_run_in_threadpool.side_effect = ValueError("Invalid ID Token")
        token = "android-token"

        mock_client_instance = mock_httpx_client.return_value.__aenter__.return_value
        mock_get = AsyncMock()
        mock_client_instance.get = mock_get

        userinfo_response = MagicMock()
        userinfo_response.status_code = 200
        userinfo_response.json.return_value = {
            "email": "android-user@example.com",
            "name": "Android User",
            "picture": "http://pic.com/android"
        }

        tokeninfo_response = MagicMock()
        tokeninfo_response.status_code = 200
        # Valid ANDROID audience
        tokeninfo_response.json.return_value = {
            "aud": "valid-android-id",
            "scope": "email"
        }

        async def get_side_effect(url, headers=None, params=None):
            if "tokeninfo" in url:
                return tokeninfo_response
            if "userinfo" in url:
                return userinfo_response
            return MagicMock(status_code=404)

        mock_get.side_effect = get_side_effect

        result = asyncio.run(main.verify_google_token(token))

        self.assertIsNotNone(result)
        self.assertEqual(result['email'], "android-user@example.com")

if __name__ == '__main__':
    unittest.main()
