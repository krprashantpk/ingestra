"""Embedding generation for document ingestion."""

from .azureopenai import AzureOpenAIEmbeddings
from .base import BaseEmbeddings

__all__ = ["AzureOpenAIEmbeddings", "BaseEmbeddings"]
