import hashlib
import math
import re
from collections import Counter
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.api.types import EmbeddingFunction, Documents, Embeddings

from config import KNOWLEDGE_DIR, CHROMA_DIR, EMBEDDING_MODEL, RAG_TOP_K, RAG_CHUNK_SIZE


class _HashEmbeddingFunction(EmbeddingFunction):
    def __init__(self, dim: int = 384):
        self._dim = dim

    def __call__(self, input: Documents) -> Embeddings:
        return [self._embed(text) for text in input]

    def _embed(self, text: str) -> list[float]:
        """Create a deterministic embedding from text using hashed n-grams."""
        text = text.lower()
        # Tokenize: split on non-alphanumeric characters
        words = re.findall(r'[a-z0-9]+', text)

        # Build n-gram features (unigrams + bigrams for some context)
        features = list(words)  # unigrams
        for i in range(len(words) - 1):
            features.append(f"{words[i]}_{words[i+1]}")  # bigrams

        # Hash each feature into a vector dimension and accumulate
        vec = [0.0] * self._dim
        counts = Counter(features)
        for feature, count in counts.items():
            h = hashlib.md5(feature.encode()).hexdigest()
            idx = int(h[:8], 16) % self._dim
            sign = 1.0 if int(h[8:10], 16) % 2 == 0 else -1.0
            vec[idx] += sign * count

        # L2 normalize so cosine distance works properly
        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]

        return vec


def _get_embedding_function():
    try:
        from chromadb.utils import embedding_functions
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
        ef(["test"])
        return ef
    except Exception:
        return _HashEmbeddingFunction(dim=384)


class RAGEngine:
    def __init__(self):
        self._client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        self._ef = _get_embedding_function()
        self._collection = self._client.get_or_create_collection(
            name="knowledge_base",
            embedding_function=self._ef,
            metadata={"hnsw:space": "cosine"},
        )
        self._indexed = False

    def index_knowledge_base(self, force: bool = False):
        """Index all markdown files in the knowledge directory."""
        if self._indexed and not force:
            return

        # Clear existing data on re-index
        if force and self._collection.count() > 0:
            self._client.delete_collection("knowledge_base")
            self._collection = self._client.get_or_create_collection(
                name="knowledge_base",
                embedding_function=self._ef,
                metadata={"hnsw:space": "cosine"},
            )

        if self._collection.count() > 0:
            self._indexed = True
            return

        documents = []
        metadatas = []
        ids = []

        for md_file in sorted(KNOWLEDGE_DIR.glob("*.md")):
            chunks = self._chunk_markdown(md_file)
            for i, chunk in enumerate(chunks):
                doc_id = f"{md_file.stem}_{i}"
                documents.append(chunk["text"])
                metadatas.append({
                    "source": md_file.name,
                    "section": chunk["section"],
                    "chunk_index": i,
                })
                ids.append(doc_id)

        if documents:
            self._collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )

        self._indexed = True

    def retrieve(self, query: str, top_k: Optional[int] = None) -> list[dict]:
        if not self._indexed:
            self.index_knowledge_base()

        k = top_k or RAG_TOP_K
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(k, self._collection.count()),
        )

        retrieved = []
        for i in range(len(results["documents"][0])):
            distance = results["distances"][0][i] if results["distances"] else 0
            # ChromaDB cosine distance: 0 = identical, 2 = opposite
            # Convert to similarity score: 1 - (distance / 2)
            similarity = 1 - (distance / 2)

            retrieved.append({
                "text": results["documents"][0][i],
                "source": results["metadatas"][0][i]["source"],
                "section": results["metadatas"][0][i]["section"],
                "relevance_score": round(similarity, 3),
            })

        return retrieved

    def _chunk_markdown(self, filepath: Path) -> list[dict]:
        text = filepath.read_text(encoding="utf-8")
        sections = re.split(r'\n(?=##\s)', text)

        chunks = []
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue

            # Extract section title
            section_title = lines[0].strip('#').strip() if lines[0].startswith('#') else "General"
            section_text = section.strip()

            if len(section_text) <= RAG_CHUNK_SIZE:
                chunks.append({"text": section_text, "section": section_title})
            else:
                # Split long sections by paragraphs
                paragraphs = section_text.split('\n\n')
                current_chunk = ""
                for para in paragraphs:
                    if len(current_chunk) + len(para) > RAG_CHUNK_SIZE and current_chunk:
                        chunks.append({"text": current_chunk.strip(), "section": section_title})
                        current_chunk = para
                    else:
                        current_chunk += "\n\n" + para if current_chunk else para

                if current_chunk.strip():
                    chunks.append({"text": current_chunk.strip(), "section": section_title})

        return chunks

    def get_stats(self) -> dict:
        return {
            "total_chunks": self._collection.count(),
            "indexed": self._indexed,
        }
