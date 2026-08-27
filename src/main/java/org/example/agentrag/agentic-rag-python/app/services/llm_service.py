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

        # Agent model
        self.model = os.getenv(
            "OLLAMA_MODEL",
            "qwen2.5-coder:7b"
        )


        # Judge model
        self.judge_model = os.getenv(
            "OLLAMA_JUDGE_MODEL",
            "qwen2.5:7b-instruct"
        )


        self.max_context_tokens = 32000


        self.encoder = tiktoken.get_encoding(
            "cl100k_base"
        )


        logger.info(
            f"Agent model : {self.model}"
        )

        logger.info(
            f"Judge model : {self.judge_model}"
        )



    # ======================================
    # Token counter
    # ======================================

    def count_tokens(
            self,
            messages: List[Dict[str,Any]]
    ):

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
            messages
    ):


        tokens = self.count_tokens(
            messages
        )


        logger.info(
            f"Prompt tokens : {tokens}"
        )


        if tokens > self.max_context_tokens:

            raise Exception(
                f"Context too large {tokens}"
            )



    # ======================================
    # Ollama common call
    # ======================================

    async def _call_ollama(

            self,

            model,

            messages,

            temperature,

            max_tokens,

            json_mode=False

    ):


        self.validate_context(
            messages
        )


        kwargs = {}


        if json_mode:

            kwargs["format"] = "json"



        response = ollama.chat(

            model=model,

            messages=messages,


            options={

                "temperature": temperature,

                "num_predict": max_tokens,

                "top_p":0.1

            },


            **kwargs

        )



        logger.info(
            response
        )



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

            messages,

            temperature=0,

            max_tokens=2000,

            json_mode=False

    ):


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

            messages,

            temperature=0,

            max_tokens=100

    ):


        return await self._call_ollama(

            model=self.judge_model,

            messages=messages,

            temperature=temperature,

            max_tokens=max_tokens,

            json_mode=True

        )




llm_service = LLMService()