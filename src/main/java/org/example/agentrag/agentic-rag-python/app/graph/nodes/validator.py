import logging
from typing import Any, Dict

from app.graph.state import AgentState
from app.services.validator_service import validator_service


logger = logging.getLogger(__name__)


async def validator_node(
        state: AgentState,
) -> AgentState:

    logger.info(
        "========== VALIDATOR NODE =========="
    )

    # ==================================================================
    # 0. STATE VALIDATION
    # ==================================================================

    if not isinstance(
            state,
            dict,
    ):

        logger.error(
            "Invalid LangGraph state."
        )

        return state

    try:

        # ==============================================================
        # 1. INFRASTRUCTURE
        # ==============================================================

        infrastructure = state.get(
            "infrastructure",
            {},
        )

        if not isinstance(
                infrastructure,
                dict,
        ):

            return _set_validation_error(
                state=state,
                error="Invalid infrastructure structure.",
                summary=(
                    "Terraform infrastructure structure is invalid."
                ),
                context_found=False,
                validation_performed=False,
            )

        resources = infrastructure.get(
            "resources",
            [],
        )

        if not isinstance(
                resources,
                list,
        ):

            return _set_validation_error(
                state=state,
                error=(
                    "Invalid Terraform resources structure."
                ),
                summary=(
                    "Terraform resources structure is invalid."
                ),
                context_found=False,
                validation_performed=False,
            )

        if not resources:

            return _set_validation_error(
                state=state,
                error=(
                    "No valid Terraform resources were found."
                ),
                summary=(
                    "Terraform resources could not be validated."
                ),
                context_found=False,
                validation_performed=False,
            )

        logger.info(
            "Terraform resources=%d",
            len(resources),
        )

        # ==============================================================
        # 2. DOCUMENTS
        # ==============================================================

        retrieved_documents = state.get(
            "retrieved_documents",
            [],
        )

        reranked_documents = state.get(
            "reranked_documents",
            [],
        )

        if not isinstance(
                retrieved_documents,
                list,
        ):
            retrieved_documents = []

        if not isinstance(
                reranked_documents,
                list,
        ):
            reranked_documents = []

        input_context_found = bool(
            retrieved_documents
            or
            reranked_documents
        )

        logger.info(
            "Retrieved documents=%d",
            len(retrieved_documents),
        )

        logger.info(
            "Reranked documents=%d",
            len(reranked_documents),
        )

        # ==============================================================
        # 3. PARSER STATUS
        # ==============================================================

        parse_status = state.get(
            "parse_status"
        )

        parse_error = state.get(
            "parse_error"
        )

        logger.info(
            "Terraform parse_status=%s",
            parse_status,
        )

        if (
                parse_status == "failed"
                or
                parse_error
        ):

            return _set_validation_error(
                state=state,
                error=(
                        parse_error
                        or
                        "Terraform parsing failed."
                ),
                summary=(
                    "Terraform validation could not be performed "
                    "because Terraform parsing failed."
                ),
                context_found=input_context_found,
                validation_performed=False,
            )

        # ==============================================================
        # 4. FIX REQUEST
        # ==============================================================

        # IMPORTANT:
        #
        # The Validator does NOT decide whether a fix is requested.
        #
        # This value must come from the planner/user intent.
        #
        # Findings do NOT automatically activate Fixer.
        #

        fix_requested = bool(
            state.get(
                "fix_requested",
                False,
            )
        )

        logger.info(
            "Explicit fix_requested=%s",
            fix_requested,
        )

        # ==============================================================
        # 5. CALL VALIDATOR SERVICE
        # ==============================================================

        logger.info(
            "Calling ValidatorService..."
        )

        result = await validator_service.validate(
            infrastructure=infrastructure,
            retrieved_documents=retrieved_documents,
            reranked_documents=reranked_documents,
            parse_status=parse_status,
            parse_error=parse_error,
        )

        # ==============================================================
        # 6. RESULT TYPE
        # ==============================================================

        if not isinstance(
                result,
                dict,
        ):

            return _set_validation_error(
                state=state,
                error=(
                    "ValidatorService returned an invalid result."
                ),
                summary=(
                    "ValidatorService returned an invalid response."
                ),
                context_found=input_context_found,
                validation_performed=False,
            )

        # ==============================================================
        # 7. SAVE RAW RESULT
        # ==============================================================

        state["validator_result"] = result

        # ==============================================================
        # 8. READ RESULT
        # ==============================================================

        validation_status = str(
            result.get(
                "status",
                "Validation Error",
            )
        ).strip()

        if not validation_status:

            validation_status = "Validation Error"

        validation_performed = bool(
            result.get(
                "validation_performed",
                False,
            )
        )

        analysis_conclusive = bool(
            result.get(
                "analysis_conclusive",
                False,
            )
        )

        context_found = bool(
            result.get(
                "context_found",
                input_context_found,
            )
        )

        findings = result.get(
            "findings",
            [],
        )

        recommendations = result.get(
            "recommendations",
            [],
        )

        score = result.get(
            "score",
            0,
        )

        validation_summary = str(
            result.get(
                "validation_summary",
                "",
            )
            or
            ""
        ).strip()

        service_error = result.get(
            "error"
        )

        if service_error is not None:

            service_error = str(
                service_error
            ).strip()

        logger.info(
            "========== VALIDATOR SERVICE RESULT =========="
        )

        logger.info(
            "Status=%s",
            validation_status,
        )

        logger.info(
            "Validation performed=%s",
            validation_performed,
        )

        logger.info(
            "Analysis conclusive=%s",
            analysis_conclusive,
        )

        logger.info(
            "Context found=%s",
            context_found,
        )

        logger.info(
            "Score=%s",
            score,
        )

        logger.info(
            "Findings=%d",
            len(findings)
            if isinstance(
                findings,
                list,
            )
            else 0,
        )

        logger.info(
            "Service error=%s",
            service_error,
        )

        # ==============================================================
        # 9. STATUS VALIDATION
        # ==============================================================

        allowed_statuses = {
            "Compliant",
            "Non-Compliant",
            "Validation Error",
        }

        if validation_status not in allowed_statuses:

            return _set_validation_error(
                state=state,
                error=(
                    "Invalid ValidatorService status: "
                    f"{validation_status}"
                ),
                summary=(
                    "ValidatorService returned an unsupported "
                    "validation status."
                ),
                context_found=context_found,
                validation_performed=validation_performed,
            )

        # ==============================================================
        # 10. FINDINGS TYPE
        # ==============================================================

        if not isinstance(
                findings,
                list,
        ):

            return _set_validation_error(
                state=state,
                error="Invalid findings structure.",
                summary=(
                    "ValidatorService returned invalid findings."
                ),
                context_found=context_found,
                validation_performed=validation_performed,
            )

        # ==============================================================
        # 11. RECOMMENDATIONS TYPE
        # ==============================================================

        if not isinstance(
                recommendations,
                list,
        ):

            recommendations = []

        # ==============================================================
        # 12. SCORE VALIDATION
        # ==============================================================

        try:

            score = int(
                score
            )

        except (
                TypeError,
                ValueError,
        ):

            return _set_validation_error(
                state=state,
                error="Invalid score.",
                summary=(
                    "ValidatorService returned an invalid score."
                ),
                context_found=context_found,
                validation_performed=validation_performed,
            )

        if not (
                0
                <=
                score
                <=
                100
        ):

            return _set_validation_error(
                state=state,
                error="Score outside 0-100.",
                summary=(
                    "ValidatorService returned an invalid score."
                ),
                context_found=context_found,
                validation_performed=validation_performed,
            )

        # ==============================================================
        # 13. VALIDATION ERROR
        # ==============================================================

        if validation_status == "Validation Error":

            return _set_validation_error(
                state=state,
                error=(
                        service_error
                        or
                        validation_summary
                        or
                        "Validator analysis was inconclusive."
                ),
                summary=(
                        validation_summary
                        or
                        "No reliable compliance conclusion could "
                        "be produced."
                ),
                context_found=context_found,
                validation_performed=validation_performed,
            )

        # ==============================================================
        # 14. VALIDATION NOT PERFORMED
        # ==============================================================

        if not validation_performed:

            return _set_validation_error(
                state=state,
                error=(
                        service_error
                        or
                        "Validation did not complete."
                ),
                summary=(
                        validation_summary
                        or
                        "Infrastructure validation did not complete."
                ),
                context_found=context_found,
                validation_performed=False,
            )

        # ==============================================================
        # 15. ANALYSIS INCONCLUSIVE
        # ==============================================================

        if not analysis_conclusive:

            return _set_validation_error(
                state=state,
                error=(
                        service_error
                        or
                        "Validator analysis was inconclusive."
                ),
                summary=(
                        validation_summary
                        or
                        "No reliable compliance conclusion could "
                        "be produced."
                ),
                context_found=context_found,
                validation_performed=True,
            )

        # ==============================================================
        # 16. RESULT CONSISTENCY
        # ==============================================================

        # Findings require Non-Compliant.

        if (
                findings
                and
                validation_status != "Non-Compliant"
        ):

            return _set_validation_error(
                state=state,
                error=(
                    "Findings exist but validation status "
                    "is not Non-Compliant."
                ),
                summary=(
                    "ValidatorService returned an inconsistent result."
                ),
                context_found=context_found,
                validation_performed=True,
            )

        # Non-Compliant requires findings.

        if (
                not findings
                and
                validation_status == "Non-Compliant"
        ):

            return _set_validation_error(
                state=state,
                error=(
                    "Non-Compliant status without findings."
                ),
                summary=(
                    "ValidatorService returned an inconsistent result."
                ),
                context_found=context_found,
                validation_performed=True,
            )

        # Compliant requires no findings.

        if (
                findings
                and
                validation_status == "Compliant"
        ):

            return _set_validation_error(
                state=state,
                error=(
                    "Compliant status contains findings."
                ),
                summary=(
                    "ValidatorService returned an inconsistent result."
                ),
                context_found=context_found,
                validation_performed=True,
            )

        # ==============================================================
        # 17. STORE VALIDATION RESULT
        # ==============================================================

        state["findings"] = findings

        state["recommendations"] = recommendations

        state["score"] = score

        state["validation_summary"] = (
            validation_summary
        )

        state["validation_status"] = (
            validation_status
        )

        state["overall_status"] = (
            validation_status
        )

        # Prevent old statuses like "reranked" from leaking.

        state["status"] = (
            validation_status
        )

        state["validation_performed"] = (
            validation_performed
        )

        state["analysis_conclusive"] = (
            analysis_conclusive
        )

        state["context_found"] = (
            context_found
        )

        # ==============================================================
        # 18. FIX REQUEST
        # ==============================================================

        # IMPORTANT:
        #
        # Never:
        #
        # state["fix_requested"] = bool(findings)
        #
        # The user/planner decides whether remediation is requested.
        #

        state["fix_requested"] = (
            fix_requested
        )

        # ==============================================================
        # 19. CLEAR ONLY VALIDATOR ERROR AFTER SUCCESS
        # ==============================================================

        state["error"] = None

        # ==============================================================
        # 20. LOG VALIDATION
        # ==============================================================

        logger.info(
            "========== VALIDATION FINISHED =========="
        )

        logger.info(
            "Status=%s",
            validation_status,
        )

        logger.info(
            "Validation performed=%s",
            validation_performed,
        )

        logger.info(
            "Analysis conclusive=%s",
            analysis_conclusive,
        )

        logger.info(
            "Context found=%s",
            context_found,
        )

        logger.info(
            "Score=%d/100",
            score,
        )

        logger.info(
            "Findings=%d",
            len(findings),
        )

        logger.info(
            "Recommendations=%d",
            len(recommendations),
        )

        logger.info(
            "Fix requested=%s",
            fix_requested,
        )

        # ==============================================================
        # 21. SAFE FINDING LOGGING
        # ==============================================================

        for index, finding in enumerate(
                findings,
                start=1,
        ):

            if not isinstance(
                    finding,
                    dict,
            ):
                continue

            location = str(
                finding.get(
                    "terraform_location",
                    "",
                )
            )

            observed = finding.get(
                "observed_value"
            )

            if _is_secret_location(
                    location
            ):

                observed = "[REDACTED]"

            logger.info(
                "Finding #%d | "
                "resource=%s | "
                "name=%s | "
                "severity=%s | "
                "terraform_location=%s | "
                "observed=%s | "
                "evidence_document=%s",
                index,
                finding.get(
                    "resource"
                ),
                finding.get(
                    "resource_name"
                ),
                finding.get(
                    "severity"
                ),
                location,
                observed,
                finding.get(
                    "evidence_document"
                ),
            )

        # ==============================================================
        # 22. RETURN
        # ==============================================================

        return state

    except Exception as exc:

        logger.exception(
            "Validator node failed."
        )

        return _set_validation_error(
            state=state,
            error=str(exc),
            summary=(
                "Validator node encountered an unexpected error."
            ),
            context_found=bool(
                state.get(
                    "retrieved_documents"
                )
                or
                state.get(
                    "reranked_documents"
                )
            ),
            validation_performed=False,
        )


# ======================================================================
# SECRET LOCATION
# ======================================================================

def _is_secret_location(
        terraform_location: str,
) -> bool:

    if not isinstance(
            terraform_location,
            str,
    ):
        return False

    last_part = (
        terraform_location
        .split(".")[-1]
        .lower()
    )

    secret_tokens = (
        "password",
        "secret",
        "token",
        "private_key",
        "privatekey",
        "api_key",
        "apikey",
        "access_key",
        "accesskey",
        "credential",
    )

    return any(
        token in last_part
        for token in secret_tokens
    )


# ======================================================================
# VALIDATION ERROR
# ======================================================================

def _set_validation_error(
        state: AgentState,
        error: str,
        summary: str,
        context_found: bool,
        validation_performed: bool,
) -> AgentState:

    # --------------------------------------------------------------
    # Validator output
    # --------------------------------------------------------------

    state["findings"] = []

    state["recommendations"] = []

    state["score"] = 0

    state["validation_summary"] = (
            summary
            or
            "Infrastructure validation failed."
    )

    # --------------------------------------------------------------
    # Canonical status
    # --------------------------------------------------------------

    state["validation_status"] = (
        "Validation Error"
    )

    state["overall_status"] = (
        "Validation Error"
    )

    state["status"] = (
        "Validation Error"
    )

    # --------------------------------------------------------------
    # Metadata
    # --------------------------------------------------------------

    state["validation_performed"] = (
        bool(
            validation_performed
        )
    )

    state["analysis_conclusive"] = False

    state["context_found"] = (
        bool(
            context_found
        )
    )

    # --------------------------------------------------------------
    # IMPORTANT
    #
    # Never launch Fixer after an invalid/inconclusive validation.
    # --------------------------------------------------------------

    state["fix_requested"] = False

    # --------------------------------------------------------------
    # Error
    # --------------------------------------------------------------

    state["error"] = str(
        error
    )

    return state