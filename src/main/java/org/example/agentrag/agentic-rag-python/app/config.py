import os
from dotenv import load_dotenv


load_dotenv()



class Settings:


    OPENAI_API_KEY = os.getenv(
        "OPENAI_API_KEY"
    )


    OPENAI_MODEL = os.getenv(
        "OPENAI_MODEL",
        "gpt-4.1"
    )


    # Embedding model
    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL",
        "BAAI/bge-small-en-v1.5"
    )


    EMBEDDING_DIMENSION = int(
        os.getenv(
            "EMBEDDING_DIMENSION",
            384
        )
    )



    QDRANT_HOST = os.getenv(
        "QDRANT_HOST",
        "localhost"
    )



    QDRANT_PORT = int(
        os.getenv(
            "QDRANT_PORT",
            6333
        )
    )



    QDRANT_COLLECTION = os.getenv(
        "QDRANT_COLLECTION",
        "azure_docs"
    )



settings = Settings()