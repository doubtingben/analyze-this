import unittest
from unittest.mock import patch, MagicMock
import sys
import os
import json

# Add backend directory to path to import analysis
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from analysis import analyze_content

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

if __name__ == '__main__':
    unittest.main()
