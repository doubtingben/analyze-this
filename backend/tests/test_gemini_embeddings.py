
import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis import generate_embedding

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
