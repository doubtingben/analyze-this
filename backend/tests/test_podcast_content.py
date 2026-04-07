import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcast_content import build_podcast_script, get_episode_body_source


class TestPodcastContent(unittest.TestCase):
    def test_build_podcast_script_preserves_paragraph_breaks(self):
        script = build_podcast_script(
            {
                "title": "Example Article",
                "type": "text",
                "content": "First paragraph line one.\nLine two.\n\nSecond paragraph starts here.",
            },
            {},
        )

        self.assertIn("Example Article", script)
        self.assertIn("First paragraph line one. Line two.\n\nSecond paragraph starts here.", script)

    @patch("podcast_content.requests.get")
    def test_build_podcast_script_uses_analysis_as_intro_and_source_url_as_body(self, mock_get):
        response = Mock()
        response.headers = {"content-type": "text/html; charset=utf-8"}
        response.text = """
        <html>
          <body>
            <article>
              <h1>Article Title</h1>
              <p>First source paragraph.</p>
              <p>Second source paragraph.</p>
            </article>
          </body>
        </html>
        """
        response.content = response.text.encode("utf-8")
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        item = {
            "title": "Screenshot share",
            "type": "screenshot",
            "content": "uploads/dev@example.com/screenshot.png",
            "item_metadata": {
                "sourceUrl": "https://example.com/article"
            },
        }
        analysis = {
            "overview": "This piece argues that teams should simplify delivery paths.",
            "podcast_title": "Simplify delivery",
        }

        script = build_podcast_script(item, analysis)

        self.assertIn("First, a quick analysis.", script)
        self.assertIn("This piece argues that teams should simplify delivery paths.", script)
        self.assertIn("Now let's get into the original piece.", script)
        self.assertIn("First source paragraph.", script)
        self.assertIn("Second source paragraph.", script)
        self.assertEqual(get_episode_body_source(item, analysis), "source_url")


if __name__ == "__main__":
    unittest.main()
