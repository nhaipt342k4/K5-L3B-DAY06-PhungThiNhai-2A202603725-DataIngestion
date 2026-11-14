"""Local embedding provider (sentence-transformers). No mock fallback."""
from typing import Protocol


class Embedder(Protocol):
    model_name: str
    dimensions: int

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Return one vector per input text, in the same order."""
        ...

    def embed_query(self, question: str) -> list[float]:
        """Return a query vector compatible with the stored document vectors."""
        ...


class MyEmbedder:
    """sentence-transformers adapter. E5 models need 'query: ' / 'passage: ' prefixes."""

    def __init__(self, model_name: str, batch_size: int = 32) -> None:
        from sentence_transformers import SentenceTransformer  # fails loudly if not installed

        self.model_name = model_name
        self.batch_size = batch_size
        self.model = SentenceTransformer(model_name, device="cpu")
        get_dim = getattr(self.model, "get_embedding_dimension", None) or self.model.get_sentence_embedding_dimension
        self.dimensions = int(get_dim())
        self.max_seq_length = int(self.model.max_seq_length)
        is_e5 = "e5" in model_name.lower()
        self.query_prefix = "query: " if is_e5 else ""
        self.passage_prefix = "passage: " if is_e5 else ""

    def token_count(self, text: str) -> int:
        return len(self.model.tokenizer(self.passage_prefix + text)["input_ids"])

    def _encode(self, texts: list[str]) -> list[list[float]]:
        vectors = self.model.encode(texts, batch_size=self.batch_size,
                                    normalize_embeddings=True, show_progress_bar=False)
        return [v.tolist() for v in vectors]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._encode([self.passage_prefix + t for t in texts])

    def embed_query(self, question: str) -> list[float]:
        return self._encode([self.query_prefix + question])[0]
