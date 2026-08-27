import logging
from typing import Any, Dict, List

from app.services.reranker import reranker_service


logger = logging.getLogger(__name__)


# ======================================================================
# NORMAL QUERY
# ======================================================================

def build_reranking_query(
        state: Dict[str, Any],
) -> str:

    current_query = state.get(
        "current_query"
    )

    if (
            isinstance(
                current_query,
                str,
            )
            and current_query.strip()
    ):

        return current_query.strip()

    prompt = state.get(
        "prompt",
        "",
    )

    if (
            isinstance(
                prompt,
                str,
            )
            and prompt.strip()
    ):

        return prompt.strip()

    return ""


# ======================================================================
# IaC DETECTION
# ======================================================================

def is_iac_state(
        state: Dict[str, Any],
) -> bool:

    terraform_code = state.get(
        "terraform_code",
        "",
    )

    infrastructure = state.get(
        "infrastructure",
        {},
    )

    resources = (
        infrastructure.get(
            "resources",
            [],
        )
        if isinstance(
            infrastructure,
            dict,
        )
        else []
    )

    return (
            isinstance(
                terraform_code,
                str,
            )
            and bool(
        terraform_code.strip()
    )
            and isinstance(
        resources,
        list,
    )
            and bool(resources)
    )


# ======================================================================
# RERANKER NODE
# ======================================================================

async def reranker_node(
        state: Dict[str, Any],
) -> Dict[str, Any]:

    logger.info(
        "========== RERANKER NODE =========="
    )

    documents = state.get(
        "retrieved_documents",
        [],
    )

    if not isinstance(
            documents,
            list,
    ):
        documents = []

    if not documents:

        return {
            "retrieved_documents": [],
            "reranked_documents": [],
            "context_found": False,
            "status": "reranking_skipped",
        }

    # ==================================================================
    # IaC MODE
    # ==================================================================

    if is_iac_state(state):

        logger.info(
            "========== PROPERTY-AWARE IaC RERANKING =========="
        )

        try:

            reranked_documents = (
                reranker_service.rerank_by_property(
                    documents=documents,
                    top_k_per_property=3,
                )
            )

        except Exception as exc:

            logger.exception(
                "Property-aware reranking failed: %s",
                exc,
            )

            # Important:
            # preserve ALL property-aware documents rather than
            # taking only documents[:5].
            fallback = documents

            return {
                "retrieved_documents": documents,
                "reranked_documents": fallback,
                "context_found": bool(fallback),
                "status": "reranking_failed",
            }

    # ==================================================================
    # NORMAL RAG
    # ==================================================================

    else:

        logger.info(
            "========== NORMAL RAG RERANKING =========="
        )

        query = build_reranking_query(
            state
        )

        if not query:

            fallback = documents[:5]

            return {
                "retrieved_documents": documents,
                "reranked_documents": fallback,
                "context_found": bool(fallback),
                "status": "reranking_skipped",
            }

        try:

            reranked_documents = (
                reranker_service.rerank(
                    query=query,
                    documents=documents,
                    top_k=5,
                )
            )

        except Exception as exc:

            logger.exception(
                "Normal reranking failed: %s",
                exc,
            )

            fallback = documents[:5]

            return {
                "retrieved_documents": documents,
                "reranked_documents": fallback,
                "context_found": bool(fallback),
                "status": "reranking_failed",
            }

    # ==================================================================
    # VALIDATE
    # ==================================================================

    valid_documents: List[
        Dict[str, Any]
    ] = []

    for document in reranked_documents:

        if not isinstance(
                document,
                dict,
        ):
            continue

        content = str(
            document.get(
                "content",
                "",
            )
        ).strip()

        if not content:
            continue

        valid_documents.append(
            document
        )

    if not valid_documents:

        fallback = documents

        return {
            "retrieved_documents": documents,
            "reranked_documents": fallback,
            "context_found": bool(fallback),
            "status": "reranking_empty",
        }

    # ==================================================================
    # PROPERTY COVERAGE
    # ==================================================================

    coverage: Dict[
        str,
        int
    ] = {}

    for document in valid_documents:

        path = str(
            document.get(
                "_terraform_path",
                document.get(
                    "terraform_path",
                    "",
                ),
            )
        ).strip()

        if not path:
            continue

        coverage[path] = (
                coverage.get(
                    path,
                    0,
                )
                + 1
        )

    logger.info(
        "Property coverage count=%d",
        len(coverage),
    )

    for path, count in coverage.items():

        logger.info(
            "PROPERTY COVERAGE | path=%s | documents=%d",
            path,
            count,
        )

    # ==================================================================
    # DETAILED LOGGING
    # ==================================================================

    for index, document in enumerate(
            valid_documents,
            start=1,
    ):

        logger.info(
            (
                "RERANKED #%d | "
                "score=%s | "
                "path=%s | "
                "property=%s | "
                "resource=%s.%s | "
                "source=%s | page=%s"
            ),
            index,
            document.get(
                "rerank_score"
            ),
            document.get(
                "_terraform_path",
                document.get(
                    "terraform_path",
                    "",
                ),
            ),
            document.get(
                "_terraform_property",
                document.get(
                    "terraform_property",
                    "",
                ),
            ),
            document.get(
                "_resource_type",
                document.get(
                    "resource_type",
                    "",
                ),
            ),
            document.get(
                "_resource_name",
                document.get(
                    "resource_name",
                    "",
                ),
            ),
            document.get(
                "source"
            ),
            document.get(
                "page"
            ),
        )

    return {
        "retrieved_documents": documents,
        "reranked_documents": valid_documents,
        "context_found": True,
        "status": "reranked",
    }