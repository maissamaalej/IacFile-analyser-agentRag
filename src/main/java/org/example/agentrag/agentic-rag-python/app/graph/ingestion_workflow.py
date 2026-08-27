from pathlib import Path
import hashlib

from app.services.loader import pdf_loader
from app.services.chunking import chunker
from app.services.embedding_service import embedding_service
from app.services.qdrant import qdrant



def generate_chunk_id(
        source: str,
        page: int,
        index: int
):



    value = f"{source}_{page}_{index}"

    return hashlib.md5(
        value.encode()
    ).hexdigest()



class IngestionPipeline:


    BATCH_SIZE = 100



    async def ingest_pdf(
            self,
            pdf_path: str
    ):


        print(
            f"\nLoading {pdf_path}"
        )


        # ==========================
        # 1) PDF Loader
        # ==========================

        documents = await pdf_loader.load(
            pdf_path
        )
        print("=" * 100)
        print("FIRST 5 DOCUMENTS")
        print("=" * 100)

        for i, doc in enumerate(documents[:5]):
            print(f"\nDocument {i+1}")
        print("Category:", getattr(doc, "category", None))
        print("Page:", getattr(doc.metadata, "page_number", None))
        print("Text:")
        print(repr(str(doc)))
        print("-" * 100)


        print(
            f"{len(documents)} elements loaded"
        )


        # ==========================
        # 2) Chunking
        # ==========================

        chunks = chunker.split(
            documents,
            pdf_path
        )


        print("=" * 100)
        print("FIRST 5 CHUNKS")
        print("=" * 100)

        for i in range(5):
            print(f"\nChunk {i+1}")
            print(chunks[i]["content"])
            print("-" * 100)


        print(
            f"{len(chunks)} chunks created"
        )



        indexed_chunks = []



        # ==========================
        # 3) Embeddings
        # ==========================

        total = len(chunks)


        for start in range(
                0,
                total,
                self.BATCH_SIZE
        ):


            end = min(
                start + self.BATCH_SIZE,
                total
            )


            batch = chunks[start:end]


            print(
                f"Embedding chunks {start}/{total}"
            )


            texts = [
                c["content"]
                for c in batch
            ]


            embeddings = await embedding_service.embed_batch(
                texts
            )



            for offset, (chunk, embedding) in enumerate(
                    zip(batch, embeddings)
            ):


                global_index = start + offset


                metadata = chunk["metadata"]



                indexed_chunks.append(

                    {


                        "id":
                            generate_chunk_id(

                                source=pdf_path,

                                page=metadata.get(
                                    "page",
                                    0
                                ),

                                index=global_index

                            ),



                        "content":
                            chunk["content"],



                        "embedding":
                            embedding,



                        "metadata":
                            {

                                "source":
                                    pdf_path,


                                "page":
                                    metadata.get(
                                        "page"
                                    ),


                                "title":
                                    metadata.get(
                                        "title"
                                    ),


                                "category":
                                    "azure_best_practices"

                            }

                    }

                )



        print(
            "Saving into Qdrant..."
        )


        # ==========================
        # 4) Qdrant
        # ==========================


        await qdrant.add_documents(
            indexed_chunks
        )


        print(
            f"{len(indexed_chunks)} chunks indexed"
        )




    async def ingest_directory(
            self,
            directory:str
    ):


        await qdrant.init_collection()



        pdf_files = list(
            Path(directory).glob(
                "*.pdf"
            )
        )


        print(
            f"{len(pdf_files)} PDF files found"
        )



        for pdf in pdf_files:


            await self.ingest_pdf(
                str(pdf)
            )



pipeline = IngestionPipeline()