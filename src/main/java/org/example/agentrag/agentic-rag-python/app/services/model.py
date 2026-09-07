import os

from sentence_transformers import SentenceTransformer


class EmbeddingModel:

    def __init__(self):

        model_name = os.getenv(
            "EMBEDDING_MODEL",
            "BAAI/bge-small-en-v1.5"
        )

        self.model = SentenceTransformer(
            model_name
        )

    def encode(
        self,
        texts: list[str]
    ):

        embeddings = self.model.encode(
            texts,
            batch_size=64,
            normalize_embeddings=True,
            show_progress_bar=False
        )

        return embeddings.tolist()


embedding_model = EmbeddingModel()
