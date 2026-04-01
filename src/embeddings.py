"""Embedding utilities using Google's embedding model."""

from langchain.embeddings.base import Embeddings
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.embeddings import FakeEmbeddings
from config import settings

def get_embeddings() -> Embeddings:
    """Initialize embeddings based on configured provider."""
    if settings.embedding_provider.lower() == "google":
        return GoogleGenerativeAIEmbeddings(
            model=settings.embedding_model,
            google_api_key=settings.google_api_key
        )

    # Local fallback embeddings to avoid external quota dependency.
    return FakeEmbeddings(size=1536)
