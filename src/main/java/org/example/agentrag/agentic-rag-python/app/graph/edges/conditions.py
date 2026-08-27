from app.graph.state import AgentState

import logging

logger = logging.getLogger(__name__)

# =====================================================
# AFTER PLANNER
# =====================================================

def route_after_planner(
        state: AgentState
) -> str:

    """
    Planner routing

    direct_answer
        -> chat

    retrieve
        -> retriever

    analyze_infrastructure
        -> parser

    reject
        -> reject
    """


    action = state.get(
        "action",
        ""
    )


    if action == "direct_answer":

        return "chat"



    elif action == "retrieve":

        return "retriever"



    elif action == "analyze_infrastructure":

        return "parser"



    elif action == "reject":

        return "reject"



    # fallback safe

    return "reject"





# =====================================================
# AFTER RERANKER
# =====================================================

def route_after_reranker(
        state: AgentState
) -> str:

    terraform_code = state.get(
        "terraform_code",
        ""
    )

    is_iac = state.get(
        "is_iac",
        False
    )

    logger.info(
        "========== ROUTE AFTER RERANKER =========="
    )

    logger.info(
        "is_iac = %s",
        is_iac
    )

    logger.info(
        "terraform_code exists = %s",
        bool(terraform_code)
    )

    logger.info(
        "reranked_documents = %s",
        len(
            state.get(
                "reranked_documents",
                []
            )
        )
    )

    logger.info(
        "retrieved_documents = %s",
        len(
            state.get(
                "retrieved_documents",
                []
            )
        )
    )

    if is_iac or terraform_code:

        logger.info(
            "ROUTING -> VALIDATOR"
        )

        return "validator"

    logger.info(
        "ROUTING -> REPORTER"
    )

    return "reporter"

# =====================================================
# AFTER VALIDATOR
# =====================================================

def should_fix(
        state: AgentState
) -> str:


    """
    Validator routing

    Problems detected
        ->
        Fixer


    No problems
        ->
        Reporter

    """


    findings = state.get(
        "findings",
        []
    )


    fix_requested = state.get(
        "fix_requested",
        False
    )


    if findings and fix_requested:

        return "fixer"



    return "reporter"