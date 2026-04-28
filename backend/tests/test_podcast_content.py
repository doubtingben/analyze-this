import os
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import podcast_content
from podcast_content import (
    PodcastRetrievalRequest,
    build_podcast_script,
    get_episode_body_source,
    retrieve_podcast_content,
)


class _MockCompletion:
    def __init__(self, content):
        self.choices = [Mock(message=Mock(content=content))]


class _MockRetrieverClient:
    def __init__(self, content):
        self.chat = Mock()
        self.chat.completions = Mock()
        self.chat.completions.create = Mock(return_value=_MockCompletion(content))


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

    @patch("podcast_content.httpx.Client.get")
    @patch("podcast_content._resolve_and_validate_ip")
    def test_build_podcast_script_uses_analysis_as_intro_and_source_url_as_body(self, mock_ip, mock_get):
        mock_ip.return_value = "93.184.216.34"
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
        response.is_redirect = False
        import httpx
        response.url = httpx.URL("http://example.com/article")
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

    def test_agentic_retriever_cleans_candidate_text(self):
        request = PodcastRetrievalRequest(
            item_id="item-1",
            user_email="dev@example.com",
            item_type="text",
            title="Example",
            content="Original paragraph with navigation noise.",
            item_metadata={},
            analysis={"overview": "Overview"},
        )
        client = _MockRetrieverClient(
            '{"body_text":"Original paragraph.","body_source":"item_content",'
            '"retrieval_error":null,"retrieval_details":{"selected_source":"item_content"}}'
        )

        with (
            patch.object(podcast_content, "PODCAST_CONTENT_RETRIEVER", "agentic"),
            patch.object(podcast_content, "client", client),
        ):
            result = retrieve_podcast_content(request)

        self.assertEqual(result.body_text, "Original paragraph.")
        self.assertEqual(result.body_source, "item_content")
        self.assertIsNone(result.retrieval_error)
        self.assertEqual(result.retrieval_details["strategy"], "agentic")
        self.assertEqual(result.retrieval_details["candidate_count"], 1)
        self.assertEqual(client.chat.completions.create.call_count, 1)

    def test_agentic_retriever_falls_back_to_deterministic_text(self):
        request = PodcastRetrievalRequest(
            item_id="item-1",
            user_email="dev@example.com",
            item_type="text",
            title="Example",
            content="Original paragraph.",
            item_metadata={},
            analysis={"overview": "Overview"},
        )

        with (
            patch.object(podcast_content, "PODCAST_CONTENT_RETRIEVER", "agentic"),
            patch.object(podcast_content, "client", None),
        ):
            result = retrieve_podcast_content(request)

        self.assertEqual(result.body_text, "Original paragraph.")
        self.assertEqual(result.body_source, "item_content")
        self.assertEqual(result.retrieval_details["strategy"], "deterministic_fallback")
        self.assertIn("podcast_retriever_client_not_initialized", result.retrieval_details["agentic_error"])


if __name__ == "__main__":
    unittest.main()
