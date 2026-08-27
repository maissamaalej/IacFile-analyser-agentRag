from qdrant_client import AsyncQdrantClient

from qdrant_client.models import (
    VectorParams,
    Distance,
    PointStruct
)

from app.config import settings



class QdrantClientService:


    """
    Service responsable de la communication avec Qdrant.

    Utilisé par:
        - ingestion pipeline
        - retriever node Agentic RAG
    """



    BATCH_SIZE = 500



    def __init__(self):


        self.client = AsyncQdrantClient(

            host=settings.QDRANT_HOST,

            port=settings.QDRANT_PORT

        )


        self.collection_name = (
            settings.QDRANT_COLLECTION
        )



    # =====================================================
    # CREATE COLLECTION
    # =====================================================

    async def init_collection(self):


        collections = await self.client.get_collections()


        existing = [

            c.name

            for c in collections.collections

        ]



        if self.collection_name not in existing:


            await self.client.create_collection(

                collection_name=self.collection_name,


                vectors_config=VectorParams(

                    size=settings.EMBEDDING_DIMENSION,

                    distance=Distance.COSINE

                )

            )


            print(
                f"Collection {self.collection_name} created"
            )


        else:

            print(
                f"Collection {self.collection_name} already exists"
            )



    # =====================================================
    # INSERT DOCUMENTS
    # =====================================================

    async def add_documents(
            self,
            documents:list
    ):


        total = len(documents)



        for start in range(
                0,
                total,
                self.BATCH_SIZE
        ):


            batch = documents[
                start:start + self.BATCH_SIZE
            ]



            points = []



            for doc in batch:



                metadata = doc.get(
                    "metadata",
                    {}
                )



                points.append(

                    PointStruct(

                        id=doc["id"],


                        vector=doc["embedding"],


                        payload={

                            "content":
                                doc["content"],


                            "source":
                                metadata.get(
                                    "source"
                                ),


                            "page":
                                metadata.get(
                                    "page"
                                ),


                            "title":
                                metadata.get(
                                    "title"
                                ),


                            "category":
                                metadata.get(
                                    "category"
                                )

                        }

                    )

                )



            await self.client.upsert(

                collection_name=self.collection_name,


                points=points

            )



            print(

                f"Inserted {min(start+self.BATCH_SIZE,total)}/{total}"

            )



    # =====================================================
    # VECTOR SEARCH
    # =====================================================

    async def search(

            self,

            query_vector:list[float],

            limit:int = 10

    ):


        result = await self.client.query_points(

            collection_name=self.collection_name,


            query=query_vector,


            limit=limit,


            with_payload=True

        )



        documents = []



        for point in result.points:



            payload = point.payload



            documents.append(

                {

                    "content":
                        payload.get(
                            "content"
                        ),


                    "source":
                        payload.get(
                            "source"
                        ),


                    "page":
                        payload.get(
                            "page"
                        ),


                    "title":
                        payload.get(
                            "title"
                        ),


                    "category":
                        payload.get(
                            "category"
                        ),


                    "score":
                        point.score

                }

            )



        return documents



    # =====================================================
    # DELETE COLLECTION
    # utile quand tu changes de modèle embedding
    # =====================================================

    async def delete_collection(self):


        await self.client.delete_collection(

            collection_name=self.collection_name

        )


        print(
            "Collection deleted"
        )



    # =====================================================
    # CLOSE
    # =====================================================

    async def close(self):


        await self.client.close()


qdrant = QdrantClientService()