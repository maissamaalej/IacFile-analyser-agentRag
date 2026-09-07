import os

from dotenv import load_dotenv

load_dotenv()


class Settings:

    # ==================================================
    # LLM
    # ==================================================

    OPENAI_API_KEY = os.getenv(
        "OPENAI_API_KEY"
    )

    OPENAI_MODEL = os.getenv(
        "OPENAI_MODEL",
        "gpt-4.1"
    )

    LLM_PROVIDER = os.getenv(
        "LLM_PROVIDER",
        "ollama"
    )

    OLLAMA_MODEL = os.getenv(
        "OLLAMA_MODEL",
        "qwen2.5-coder:7b"
    )

    OLLAMA_JUDGE_MODEL = os.getenv(
        "OLLAMA_JUDGE_MODEL",
        "qwen2.5:7b-instruct"
    )

    # ==================================================
    # EMBEDDING
    # ==================================================

    EMBEDDING_MODEL = os.getenv(
        "EMBEDDING_MODEL",
        "BAAI/bge-small-en-v1.5"
    )

    EMBEDDING_DIMENSION = int(
        os.getenv(
            "EMBEDDING_DIMENSION",
            "384"
        )
    )

    # ==================================================
    # QDRANT
    # ==================================================

    QDRANT_HOST = os.getenv(
        "QDRANT_HOST",
        "agentrag-qdrant"
    )

    QDRANT_PORT = int(
        os.getenv(
            "QDRANT_PORT",
            "6333"
        )
    )

    QDRANT_COLLECTION = os.getenv(
        "QDRANT_COLLECTION",
        "azure_best_practices"
    )

    # ==================================================
    # DOCUMENTS
    # ==================================================

    DOCUMENTS_PATH = os.getenv(
        "DOCUMENTS_PATH",
        "data"
    )

    # ==================================================
    # LANGSMITH
    # ==================================================

    LANGSMITH_API_KEY = os.getenv(
        "LANGSMITH_API_KEY"
    )

    LANGSMITH_TRACING = os.getenv(
        "LANGSMITH_TRACING",
        "false"
    )

    LANGSMITH_PROJECT = os.getenv(
        "LANGSMITH_PROJECT",
        "AgentRAG"
    )


settings = Settings()
