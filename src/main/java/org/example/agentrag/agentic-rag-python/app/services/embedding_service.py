from app.services.model import embedding_model



class EmbeddingService:


    def __init__(self):

        pass

    async def embed(
            self,
            text: str
    ) -> list[float]:


        embeddings = embedding_model.encode(
            [
                text
            ]
        )


        return embeddings[0]



    async def embed_batch(
            self,
            texts: list[str]
    ) -> list[list[float]]:


        embeddings = embedding_model.encode(
            texts
        )


        return embeddings



    async def close(self):

        pass



embedding_service = EmbeddingService()