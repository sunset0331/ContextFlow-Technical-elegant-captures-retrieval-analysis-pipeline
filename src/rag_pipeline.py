"""RAG Pipeline for retrieving and augmenting data."""

import os
from typing import List, Dict, Any
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_weaviate.vectorstores import WeaviateVectorStore
from langchain.schema import Document
import weaviate
from config import settings
from embeddings import get_embeddings


class RAGPipeline:
    """Handles document ingestion, embedding, and retrieval."""
    
    def __init__(self):
        """Initialize RAG pipeline."""
        self.embeddings = get_embeddings()
        self.vector_store = None
        self.client = None
        self.local_documents: List[Document] = []
        self._initialize_weaviate()
    
    def _initialize_weaviate(self):
        """Initialize Weaviate connection."""
        try:
            self.client = weaviate.Client(
                url=settings.weaviate_url,
                api_key=settings.weaviate_api_key if settings.weaviate_api_key else None
            )
            print(f"✓ Connected to Weaviate at {settings.weaviate_url}")
        except Exception as e:
            print(f"⚠ Warning: Could not connect to Weaviate: {e}")
            print("  Starting with local vector store fallback")
    
    def ingest_documents(self, documents: List[Document], index_name: str = "DataAnalysis"):
        """
        Ingest documents into the vector store.
        
        Args:
            documents: List of LangChain Document objects
            index_name: Name of the Weaviate index
        """
        # Split documents into chunks
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            separators=["\n\n", "\n", " ", ""]
        )
        
        splits = splitter.split_documents(documents)
        print(f"✓ Split documents into {len(splits)} chunks")
        self.local_documents.extend(splits)
        
        # Create or update vector store
        if self.client:
            try:
                self.vector_store = WeaviateVectorStore.from_documents(
                    documents=splits,
                    embedding=self.embeddings,
                    client=self.client,
                    index_name=index_name
                )
                print(f"✓ Ingested {len(splits)} documents into Weaviate")
            except Exception as e:
                print(f"⚠ Could not ingest into Weaviate: {e}")
                self.vector_store = None
        else:
            self.vector_store = None
    
    def retrieve(self, query: str, k: int = None) -> List[Document]:
        """
        Retrieve relevant documents for a query.
        
        Args:
            query: Search query
            k: Number of documents to retrieve
            
        Returns:
            List of relevant documents
        """
        if k is None:
            k = settings.top_k_retrieval
        
        if self.vector_store:
            try:
                results = self.vector_store.similarity_search(query, k=k)
                return results
            except Exception as e:
                print(f"⚠ Retrieval error: {e}")
        return self._retrieve_from_local(query=query, k=k)

    def _retrieve_from_local(self, query: str, k: int) -> List[Document]:
        """Fallback lexical retrieval when vector store is unavailable."""
        if not self.local_documents:
            return []

        query_terms = {token.strip().lower() for token in query.split() if token.strip()}
        scored_docs: List[tuple[int, Document]] = []

        for doc in self.local_documents:
            text_terms = set(doc.page_content.lower().split())
            overlap = len(query_terms.intersection(text_terms))
            if overlap > 0:
                scored_docs.append((overlap, doc))

        if not scored_docs:
            return self.local_documents[:k]

        scored_docs.sort(key=lambda item: item[0], reverse=True)
        return [doc for _, doc in scored_docs[:k]]
    
    def get_context(self, query: str) -> str:
        """
        Get context string from retrieved documents.
        
        Args:
            query: Search query
            
        Returns:
            Formatted context string
        """
        docs = self.retrieve(query)
        if not docs:
            return "No relevant documents found."

        context_blocks: List[str] = []
        total_chars = 0
        max_chars = settings.max_context_chars

        for i, doc in enumerate(docs):
            # Cap each block to keep prompts compact and predictable for quota limits.
            content = doc.page_content[:700]
            block = (
                f"[{i+1}] {content}\n"
                f"  (Source: {doc.metadata.get('source', 'Unknown')})"
            )
            if total_chars + len(block) > max_chars:
                break
            context_blocks.append(block)
            total_chars += len(block)

        return "\n".join(context_blocks) if context_blocks else "No relevant documents found."


def load_text_documents(file_path: str) -> List[Document]:
    """Load documents from a text file."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    return [Document(page_content=content, metadata={"source": file_path})]


def load_csv_documents(file_path: str) -> List[Document]:
    """Load documents from a CSV file."""
    import pandas as pd
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    
    try:
        df = pd.read_csv(file_path, sep=None, engine="python", encoding="utf-8")
    except Exception:
        # Fallback for common exported CSV encodings.
        df = pd.read_csv(file_path, sep=None, engine="python", encoding="latin-1")

    if df.empty:
        raise ValueError("CSV file appears empty or could not be parsed into rows")

    documents = []
    
    for idx, row in df.iterrows():
        content = "\n".join([f"{col}: {val}" for col, val in row.items()])
        documents.append(Document(
            page_content=content,
            metadata={"source": file_path, "row": idx}
        ))
    
    return documents
