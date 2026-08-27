import os
import asyncio
import re
import logging

from dotenv import load_dotenv

load_dotenv()

os.environ["LANGCHAIN_TRACING_V2"] = "true"

if os.getenv("LANGCHAIN_API_KEY"):
    os.environ["LANGCHAIN_API_KEY"] = os.getenv(
        "LANGCHAIN_API_KEY"
    )

os.environ["LANGCHAIN_PROJECT"] = "AgentRAG"

logger = logging.getLogger(__name__)


# =====================================================
# IMPORTS
# =====================================================

from fastapi import (
    FastAPI,
    UploadFile,
    File,
    Form
)

from pydantic import BaseModel

from typing import Union

from app.services.model import embedding_model

from app.graph.graph_workflow import workflow

from app.evaluation.hallucination import (
    evaluate_groundedness
)


app = FastAPI(
    title="AgentRAG Service"
)


# =====================================================
# MODELS
# =====================================================

class AgentRequest(BaseModel):

    prompt: str

    user_id: int | None = None

    chat_id: int | None = None


class EmbeddingRequest(BaseModel):

    input: Union[
        str,
        list[str]
    ]


# =====================================================
# EMBEDDING API
# =====================================================

@app.post("/embed")
async def create_embedding(
        request: EmbeddingRequest
):

    texts = request.input

    if isinstance(texts, str):

        texts = [
            texts
        ]

    embeddings = await asyncio.to_thread(
        embedding_model.encode,
        texts
    )

    return {
        "embeddings": embeddings
    }


# =====================================================
# TERRAFORM PROCESSING
# =====================================================

def normalize_terraform(
        code: str | None
):

    if not code:
        return None

    code = code.strip()

    # Remplacer uniquement les espaces multiples.
    code = re.sub(
        r"[ \t]+",
        " ",
        code
    )

    # Remettre les blocs sur plusieurs lignes.
    code = code.replace(
        "{ ",
        "{\n"
    )

    code = code.replace(
        " }",
        "\n}"
    )

    return code.strip()


def extract_terraform(
        prompt: str
):

    if not prompt:
        return None

    start_keywords = [
        "resource",
        "provider",
        "module",
        "variable",
        "data",
        "output",
        "locals"
    ]

    start = -1

    for keyword in start_keywords:

        index = prompt.find(keyword)

        if index != -1:

            start = index

            break

    if start == -1:

        return None

    terraform = prompt[start:]

    return normalize_terraform(
        terraform
    )


# =====================================================
# STATE
# =====================================================

def build_state(
        prompt,
        terraform_code=None,
        user_id=0,
        chat_id=0
):

    return {

        "messages": [],

        "user_id": user_id,

        "chat_id": chat_id,

        "prompt": prompt,

        "terraform_code": terraform_code,

        # IMPORTANT:
        # Use the same name used by the workflow.
        "is_iac": terraform_code is not None,

        "task": None,

        "action": None,

        "plan": [],

        "current_query": None,

        "infrastructure": {},

        "retrieved_documents": [],

        "reranked_documents": [],

        "context_found": False,

        "findings": [],

        "recommendations": [],

        # IMPORTANT:
        # False until the user explicitly asks
        # for Terraform correction.
        "fix_requested": False,

        "validation_summary": None,

        "fixed_terraform": None,

        "fix_summary": None,

        "changes": [],

        "answer": None,

        "report": None,

        "score": None,

        "status": "started",

        "error": None
    }


# =====================================================
# EXECUTION
# =====================================================

async def execute_agent(
        prompt,
        terraform_code=None,
        user_id=0,
        chat_id=0
):

    logger.info(
        "========== INPUT =========="
    )

    logger.info(
        prompt
    )

    logger.info(
        "========== TERRAFORM =========="
    )

    logger.info(
        terraform_code
    )

    state = build_state(
        prompt,
        terraform_code,
        user_id,
        chat_id
    )

    logger.info(
        "========== INITIAL STATE =========="
    )

    logger.info(
        "is_iac = %s",
        state.get("is_iac")
    )

    logger.info(
        "terraform_code exists = %s",
        bool(state.get("terraform_code"))
    )

    result = await workflow.ainvoke(
        state
    )

    print(
        "\n========== WORKFLOW RESULT =========="
    )

    print(
        result
    )

    print(
        "=====================================\n"
    )

    answer = (
            result.get("answer")
            or result.get("report")
            or ""
    )

    print(
        "\n========== FINAL ANSWER =========="
    )

    print(
        answer
    )

    print(
        "==================================\n"
    )

    evaluation = await evaluate_groundedness(
        question=prompt,

        documents=result.get(
            "retrieved_documents",
            []
        ),

        answer=answer
    )

    return {

        "answer": answer,

        "findings": result.get(
            "findings",
            []
        ),

        "score": result.get(
            "score"
        ),

        "fixedTerraform": result.get(
            "fixed_terraform"
        ),

        "showFixAction": result.get(
            "fix_requested",
            False
        ),

        "grounded": evaluation.get(
            "grounded"
        ),

        "hallucination": evaluation

    }


# =====================================================
# CHAT
# =====================================================

@app.post("/chat")
async def chat(
        request: AgentRequest
):

    terraform_code = extract_terraform(
        request.prompt
    )

    if terraform_code:

        print(
            "===== TERRAFORM DETECTED ====="
        )

        print(
            terraform_code
        )

    else:

        print(
            "===== NORMAL CHAT ====="
        )

    return await execute_agent(

        prompt=request.prompt,

        terraform_code=terraform_code,

        user_id=request.user_id or 0,

        chat_id=request.chat_id or 0
    )


# =====================================================
# IAC FILE / TEXT
# =====================================================

@app.post("/analyze-iac")
async def analyze_iac(

        prompt: str = Form(""),

        file: UploadFile = File(None)
):

    terraform_code = None

    if file:

        if not file.filename.endswith(".tf"):

            return {
                "error": (
                    "Only Terraform .tf files are supported"
                )
            }

        content = await file.read()

        terraform_code = normalize_terraform(
            content.decode(
                "utf-8"
            )
        )

    if terraform_code is None:

        terraform_code = extract_terraform(
            prompt
        )

    if not terraform_code:

        return {
            "error": (
                "No Terraform code detected"
            )
        }

    return await execute_agent(

        prompt=prompt,

        terraform_code=terraform_code
    )

