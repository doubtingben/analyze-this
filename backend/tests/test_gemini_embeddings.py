
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import generate_embedding, _build_multimodal_embedding_contents

def test_generate_embedding_gemini():
    """Test that generate_embedding uses Gemini when model is set to gemini-embedding-2-preview."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_emb = MagicMock()
    mock_emb.values = [0.1, 0.2, 0.3]
    mock_response.embeddings = [mock_emb]
    mock_client.models.embed_content.return_value = mock_response
    
    with patch("analysis.google_genai_client", mock_client), \
         patch("analysis.EMBEDDING_MODEL", "gemini-embedding-2-preview"):
        
        emb = generate_embedding("hello world", task_type="RETRIEVAL_QUERY")
        
        assert emb == [0.1, 0.2, 0.3]
        mock_client.models.embed_content.assert_called_once_with(
            model="gemini-embedding-2-preview",
            contents="hello world",
            config={
                'task_type': "RETRIEVAL_QUERY",
                'output_dimensionality': 1536
            }
        )

def test_build_multimodal_embedding_contents_for_image_includes_media_part():
    with patch("analysis._read_storage_bytes", return_value=b"fake-image-bytes"):
        contents = _build_multimodal_embedding_contents(
            "A cat photo",
            item_type="image",
            content="uploads/user/image.png",
            item_metadata={"mimeType": "image/png"},
            title="Cat",
        )

    assert isinstance(contents, list)
    assert len(contents) == 2
    assert contents[0].text == "Title: Cat\nSummary: A cat photo"
    assert contents[1].inline_data.mime_type == "image/png"
    assert contents[1].inline_data.data == b"fake-image-bytes"

def test_build_multimodal_embedding_contents_for_text_stays_plain_text():
    contents = _build_multimodal_embedding_contents("hello world")
    assert contents == "hello world"

def test_generate_embedding_gemini_retries_rate_limit():
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_emb = MagicMock()
    mock_emb.values = [0.1, 0.2, 0.3]
    mock_response.embeddings = [mock_emb]
    mock_client.models.embed_content.side_effect = [
        Exception("429 Too Many Requests"),
        mock_response,
    ]

    with patch("analysis.google_genai_client", mock_client), \
         patch("analysis.EMBEDDING_MODEL", "gemini-embedding-2-preview"), \
         patch("analysis.GEMINI_EMBEDDING_MAX_RETRIES", 2), \
         patch("analysis.GEMINI_EMBEDDING_RETRY_BASE_DELAY", 0), \
         patch("analysis.time.sleep") as mock_sleep:
        emb = generate_embedding("hello world", task_type="RETRIEVAL_QUERY")

        assert emb == [0.1, 0.2, 0.3]
        assert mock_client.models.embed_content.call_count == 2
        mock_sleep.assert_called_once_with(0)

def test_generate_embedding_gemini_requires_google_api_key():
    with patch("analysis.google_genai_client", None), \
         patch("analysis.EMBEDDING_MODEL", "gemini-embedding-2-preview"), \
         patch("analysis.client") as mock_client:
        emb = generate_embedding("hello world")

        assert emb is None
        mock_client.embeddings.create.assert_not_called()

def test_generate_embedding_openai_fallback():
    """Test that it falls back to OpenAI for other models."""
    with patch("analysis.client") as mock_client, \
         patch("analysis.google_genai_client", None):
        mock_response = MagicMock()
        mock_response.data = [MagicMock(embedding=[0.4, 0.5, 0.6])]
        mock_client.embeddings.create.return_value = mock_response
        
        import analysis
        with patch("analysis.EMBEDDING_MODEL", "text-embedding-3-small"):
            emb = generate_embedding("hello world")
            
            assert emb == [0.4, 0.5, 0.6]
            mock_client.embeddings.create.assert_called_once()
