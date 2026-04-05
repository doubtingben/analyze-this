import os
import sys
import unittest

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from podcast_content import build_podcast_script


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


if __name__ == "__main__":
    unittest.main()
