import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Add backend directory to path to import analysis
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from analysis import analyze_content, get_image_data_url

class TestAnalysis(unittest.TestCase):

    @patch('analysis.client')
    @patch('analysis.get_analysis_prompt')
    def test_analyze_content_success(self, mock_get_prompt, mock_client):
        # Setup
        mock_get_prompt.return_value = "System Prompt"
        
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"step": "add_event", "details": "Dinner"}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        # execution
        result = analyze_content("Dinner at 8pm")
        
        # Verification - normalize_analysis transforms step->action and adds overview
        self.assertEqual(result, {
            "overview": "Suggested action: add_event",
            "action": "add_event",
            "details": "Dinner"
        })
        mock_client.chat.completions.create.assert_called_once()
    
    @patch('analysis.client')
    def test_analyze_content_exception(self, mock_client):
        # Setup
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        # execution
        result = analyze_content("Input")
        
        # Verification - normalize_analysis adds overview for errors
        self.assertIn("error", result)
        self.assertEqual(result["error"], "API Error")
        self.assertEqual(result["overview"], "Error: API Error")

    @patch('analysis.client')
    @patch('analysis.get_analysis_prompt')
    def test_analyze_content_invalid_json(self, mock_get_prompt, mock_client):
        # Setup
        mock_get_prompt.return_value = "System Prompt"
        
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = 'Not JSON'
        mock_client.chat.completions.create.return_value = mock_completion
        
        # execution
        result = analyze_content("Input")
        
        # Verification - normalize_analysis adds overview for errors
        self.assertIn("error", result)
        self.assertEqual(result["error"], "Invalid JSON")
        self.assertEqual(result["raw_analysis"], "Not JSON")
        self.assertEqual(result["overview"], "Error: Invalid JSON")

    @patch('analysis.client')
    @patch('analysis.get_analysis_prompt')
    def test_analyze_image_success(self, mock_get_prompt, mock_client):
        # Setup
        mock_get_prompt.return_value = "System Prompt"
        
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"step": "save_image"}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        # execution
        result = analyze_content("http://example.com/image.png", item_type='image')
        
        # Verification - normalize_analysis transforms step->action and adds overview
        self.assertEqual(result, {
            "overview": "Suggested action: save_image",
            "action": "save_image"
        })
        
        # Check call arguments
        args, kwargs = mock_client.chat.completions.create.call_args
        messages = kwargs['messages']
        user_message = messages[1]
        
        # Verify message structure
        self.assertEqual(user_message['role'], 'user')
        self.assertIsInstance(user_message['content'], list)
        self.assertEqual(user_message['content'][1]['type'], 'image_url')
        self.assertEqual(user_message['content'][1]['image_url']['url'], "http://example.com/image.png")

    @patch('analysis.client')
    @patch('analysis.get_analysis_prompt')
    def test_analyze_url_success(self, mock_get_prompt, mock_client):
        # Setup
        mock_get_prompt.return_value = "System Prompt"
        
        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"step": "add_event"}'
        mock_client.chat.completions.create.return_value = mock_completion
        
        # execution
        result = analyze_content("http://example.com", item_type='web_url')
        
        # Verification - normalize_analysis transforms step->action and adds overview
        self.assertEqual(result, {
            "overview": "Suggested action: add_event",
            "action": "add_event"
        })
        
        # Check call arguments
        args, kwargs = mock_client.chat.completions.create.call_args
        messages = kwargs['messages']
        user_message = messages[1]
        
        # Verify message structure
        self.assertEqual(user_message['role'], 'user')
        self.assertIn("Analyze the content at this URL", user_message['content'])
        self.assertIn("http://example.com", user_message['content'])

    def test_get_image_data_url_with_full_url(self):
        """Full URLs (http/https) should be returned unchanged."""
        http_url = "http://example.com/image.png"
        https_url = "https://example.com/image.jpg"

        self.assertEqual(get_image_data_url(http_url), http_url)
        self.assertEqual(get_image_data_url(https_url), https_url)

    @patch('analysis.storage')
    def test_get_image_data_url_with_storage_path(self, mock_storage):
        """Storage paths should be fetched and converted to base64 data URLs."""
        # Setup mock
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.content_type = 'image/png'
        mock_blob.download_as_bytes.return_value = b'fake-image-data'

        # Execute
        result = get_image_data_url("uploads/user@email.com/test.png")

        # Verify
        self.assertTrue(result.startswith("data:image/png;base64,"))
        mock_bucket.blob.assert_called_once_with("uploads/user@email.com/test.png")
        mock_blob.download_as_bytes.assert_called_once()

    @patch('analysis.storage')
    def test_get_image_data_url_blob_not_exists(self, mock_storage):
        """Should return None if blob doesn't exist."""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = False

        result = get_image_data_url("uploads/nonexistent.png")

        self.assertIsNone(result)

    @patch('analysis.storage')
    def test_get_image_data_url_infers_mime_type(self, mock_storage):
        """Should infer MIME type from extension if content_type is None."""
        mock_bucket = MagicMock()
        mock_blob = MagicMock()
        mock_storage.bucket.return_value = mock_bucket
        mock_bucket.blob.return_value = mock_blob
        mock_blob.exists.return_value = True
        mock_blob.content_type = None  # No content type set
        mock_blob.download_as_bytes.return_value = b'fake-image-data'

        # Test .jpg extension
        result = get_image_data_url("uploads/test.jpg")
        self.assertTrue(result.startswith("data:image/jpeg;base64,"))

        # Test .webp extension
        result = get_image_data_url("uploads/test.webp")
        self.assertTrue(result.startswith("data:image/webp;base64,"))

    @patch('analysis.client')
    @patch('analysis.get_analysis_prompt')
    @patch('analysis.get_image_data_url')
    def test_analyze_screenshot_with_storage_path(self, mock_get_url, mock_get_prompt, mock_client):
        """Screenshots with storage paths should be converted to data URLs before analysis."""
        # Setup
        mock_get_prompt.return_value = "System Prompt"
        mock_get_url.return_value = "data:image/png;base64,ZmFrZS1pbWFnZS1kYXRh"

        mock_completion = MagicMock()
        mock_completion.choices[0].message.content = '{"overview": "A screenshot", "action": "save_image"}'
        mock_client.chat.completions.create.return_value = mock_completion

        # Execute
        result = analyze_content("uploads/user@email.com/screenshot.png", item_type='screenshot')

        # Verify get_image_data_url was called with the storage path
        mock_get_url.assert_called_once_with("uploads/user@email.com/screenshot.png")

        # Verify the data URL was used in the API call
        args, kwargs = mock_client.chat.completions.create.call_args
        messages = kwargs['messages']
        user_message = messages[1]
        self.assertEqual(user_message['content'][1]['image_url']['url'], "data:image/png;base64,ZmFrZS1pbWFnZS1kYXRh")

    @patch('analysis.get_image_data_url')
    def test_analyze_image_returns_error_when_url_resolution_fails(self, mock_get_url):
        """Should return error result if image URL cannot be resolved."""
        mock_get_url.return_value = None

        result = analyze_content("uploads/nonexistent.png", item_type='image')

        self.assertIn("error", result)
        self.assertIn("Could not load image", result["error"])
        self.assertIn("overview", result)  # normalize_analysis should add overview

if __name__ == '__main__':
    unittest.main()
