import logging
import os
from typing import List, Dict, Any

from dotenv import load_dotenv
import ollama
import tiktoken


load_dotenv()


logger = logging.getLogger(__name__)


class LLMService:

    def __init__(self):

        # ======================================
        # Agent model
        # ======================================

        self.model = os.getenv(
            "OLLAMA_MODEL",
            "qwen2.5-coder:7b"
        )

        # ======================================
        # Judge model
        # ======================================

        self.judge_model = os.getenv(
            "OLLAMA_JUDGE_MODEL",
            "qwen2.5:7b-instruct"
        )

        # ======================================
        # Context configuration
        # ======================================

        self.max_context_tokens = 32000

        self.encoder = tiktoken.get_encoding(
            "cl100k_base"
        )

        # ======================================
        # Ollama configuration
        # ======================================
        #
        # IMPORTANT:
        # Do NOT hardcode 127.0.0.1 here.
        #
        # Inside Kubernetes:
        #   127.0.0.1 = the Python container itself
        #
        # Ollama is running on:
        #   192.168.1.11:11434
        #
        # Kubernetes already provides:
        #   OLLAMA_HOST=http://192.168.1.11:11434
        #
        # ======================================

        self.ollama_host = os.getenv(
            "OLLAMA_HOST",
            "http://192.168.1.11:11434"
        )

        self.client = ollama.Client(
            host=self.ollama_host
        )

        # ======================================
        # Logs
        # ======================================

        logger.info(
            f"Agent model : {self.model}"
        )

        logger.info(
            f"Judge model : {self.judge_model}"
        )

        logger.info(
            f"Ollama host : {self.ollama_host}"
        )

    # ======================================
    # Token counter
    # ======================================

    def count_tokens(
            self,
            messages: List[Dict[str, Any]]
    ) -> int:

        total = 0

        for message in messages:

            content = message.get(
                "content",
                ""
            )

            total += len(
                self.encoder.encode(content)
            )

        return total

    # ======================================
    # Context validation
    # ======================================

    def validate_context(
            self,
            messages: List[Dict[str, Any]]
    ) -> None:

        tokens = self.count_tokens(
            messages
        )

        logger.info(
            f"Prompt tokens : {tokens}"
        )

        if tokens > self.max_context_tokens:

            raise Exception(
                f"Context too large: "
                f"{tokens} tokens "
                f"(maximum: {self.max_context_tokens})"
            )

    # ======================================
    # Ollama common call
    # ======================================

    async def _call_ollama(
            self,
            model: str,
            messages: List[Dict[str, Any]],
            temperature: float,
            max_tokens: int,
            json_mode: bool = False
    ) -> str:

        # Validate context
        self.validate_context(
            messages
        )

        # ==================================
        # Ollama options
        # ==================================

        kwargs = {}

        if json_mode:

            kwargs["format"] = "json"

        logger.info(
            f"Calling Ollama | "
            f"host={self.ollama_host} | "
            f"model={model}"
        )

        # ==================================
        # Call Ollama
        # ==================================

        response = self.client.chat(

            model=model,

            messages=messages,

            options={

                "temperature": temperature,

                "num_predict": max_tokens,

                "top_p": 0.1

            },

            **kwargs

        )

        # ==================================
        # Log response
        # ==================================

        logger.info(
            f"Ollama response received | "
            f"model={model}"
        )

        # ==================================
        # Extract content
        # ==================================

        content = response.get(
            "message",
            {}
        ).get(
            "content",
            ""
        )

        if not content:

            raise Exception(
                "Empty Ollama response"
            )

        return content

    # ======================================
    # Agent generation
    # ======================================

    async def generate(
            self,
            messages: List[Dict[str, Any]],
            temperature: float = 0,
            max_tokens: int = 2000,
            json_mode: bool = False
    ) -> str:

        return await self._call_ollama(

            model=self.model,

            messages=messages,

            temperature=temperature,

            max_tokens=max_tokens,

            json_mode=json_mode

        )

    # ======================================
    # Judge generation
    # ======================================

    async def generate_judge(
            self,
            messages: List[Dict[str, Any]],
            temperature: float = 0,
            max_tokens: int = 100
    ) -> str:

        return await self._call_ollama(

            model=self.judge_model,

            messages=messages,

            temperature=temperature,

            max_tokens=max_tokens,

            json_mode=True

        )


# ==========================================
# Global LLM service instance
# ==========================================

llm_service = LLMService()
