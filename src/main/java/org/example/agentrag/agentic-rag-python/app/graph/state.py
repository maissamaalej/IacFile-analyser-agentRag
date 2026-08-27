from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator


class AgentState(TypedDict):

    # ==============================================================
    # Conversation
    # ==============================================================

    messages: Annotated[
        List[dict],
        operator.add
    ]

    # ==============================================================
    # User
    # ==============================================================

    user_id: int

    chat_id: int

    # ==============================================================
    # User Input
    # ==============================================================

    prompt: str

    terraform_code: Optional[str]

    is_iac: bool

    # ==============================================================
    # Planner
    # ==============================================================

    task: Optional[str]

    action: Optional[str]

    plan: List[str]

    current_query: Optional[str]

    # ==============================================================
    # Parsed Infrastructure
    # ==============================================================

    infrastructure: Dict[str, Any]

    # ==============================================================
    # Retrieval
    # ==============================================================

    retrieved_documents: List[Dict[str, Any]]

    reranked_documents: List[Dict[str, Any]]

    context_found: bool

    # ==============================================================
    # Validation
    # ==============================================================

    findings: List[Dict[str, Any]]

    recommendations: List[Dict[str, Any]]

    fix_requested: bool

    validation_summary: Optional[str]

    validation_status: str

    validation_performed: bool

    analysis_conclusive: bool

    overall_status: str

    # ==============================================================
    # Fixer
    # ==============================================================

    fixed_terraform: Optional[str]

    fix_summary: Optional[str]

    changes: List[Dict[str, Any]]

    # ==============================================================
    # Reporter
    # ==============================================================

    report: Optional[str]

    answer: Optional[str]

    # ==============================================================
    # Metadata
    # ==============================================================

    score: Optional[int]

    # --------------------------------------------------------------
    # Pipeline status
    #
    # IMPORTANT:
    # This is NOT the same thing as validation_status.
    #
    # Examples:
    #   "planned"
    #   "retrieved"
    #   "reranked"
    #   "validated"
    #   "reported"
    # --------------------------------------------------------------

    status: str

    # ==============================================================
    # Error
    # ==============================================================

    error: Optional[str]