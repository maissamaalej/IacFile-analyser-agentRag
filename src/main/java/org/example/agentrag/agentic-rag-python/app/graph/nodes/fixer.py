import logging

from app.graph.state import AgentState
from app.services.fixer_service import fixer_service


logger = logging.getLogger(__name__)


async def fixer_node(
        state: AgentState,
) -> AgentState:
    """
    LangGraph Fixer Node.

    Responsibilities
    ----------------
    1. Read explicit fix request.
    2. Read Validator findings.
    3. Call FixerService only when remediation was explicitly requested.
    4. Store corrected Terraform.
    5. Store accepted/rejected changes.
    6. Keep Validator state intact.

    Important
    ---------
    Findings do NOT automatically mean that a fix was requested.
    Validator remains the authority for security findings.
    Fixer does not perform security analysis.
    """

    logger.info(
        "========== FIXER NODE =========="
    )

    if not isinstance(
            state,
            dict,
    ):
        logger.error(
            "Invalid state received by Fixer."
        )
        return state

    try:

        # ==============================================================
        # 1. READ STATE
        # ==============================================================

        terraform_code = state.get(
            "terraform_code"
        )

        findings = state.get(
            "findings",
            [],
        )

        infrastructure = state.get(
            "infrastructure",
            {},
        )

        recommendations = state.get(
            "recommendations",
            [],
        )

        reranked_documents = state.get(
            "reranked_documents",
            [],
        )

        retrieved_documents = state.get(
            "retrieved_documents",
            [],
        )

        # Prefer reranked documents.
        if isinstance(
                reranked_documents,
                list,
        ) and reranked_documents:

            documents = reranked_documents

        elif isinstance(
                retrieved_documents,
                list,
        ):

            documents = retrieved_documents

        else:

            documents = []

        # --------------------------------------------------------------
        # Explicit user/planner intent.
        # --------------------------------------------------------------

        fix_requested = bool(
            state.get(
                "fix_requested",
                False,
            )
        )

        logger.info(
            "Fix requested=%s",
            fix_requested,
        )

        logger.info(
            "Terraform available=%s",
            bool(terraform_code),
        )

        logger.info(
            "Validator findings=%d",
            len(findings)
            if isinstance(
                findings,
                list,
            )
            else 0,
        )

        # ==============================================================
        # 2. INITIALIZE FIXER OUTPUT
        # ==============================================================

        state["fix_success"] = False

        state["changes"] = []

        state["rejected_changes"] = []

        state["fix_summary"] = ""

        state["fixer_error"] = None

        # ==============================================================
        # 3. FIX NOT REQUESTED
        # ==============================================================

        if not fix_requested:

            logger.info(
                "Fixer skipped: remediation was not requested."
            )

            state["fixed_terraform"] = (
                terraform_code
            )

            state["fix_success"] = True

            state["fix_summary"] = (
                "No remediation was requested."
            )

            # ----------------------------------------------------------
            # IMPORTANT
            #
            # Do not modify:
            #   state["findings"]
            #   state["score"]
            #   state["validation_status"]
            #   state["error"]
            #
            # Validator remains authoritative.
            # ----------------------------------------------------------

            return state

        # ==============================================================
        # 4. FIX REQUESTED BUT TERRAFORM IS MISSING
        # ==============================================================

        if not isinstance(
                terraform_code,
                str,
        ) or not terraform_code.strip():

            logger.warning(
                "Fix requested but Terraform code is missing."
            )

            state["fixed_terraform"] = None

            state["fix_success"] = False

            state["fix_summary"] = (
                "No Terraform code was provided."
            )

            state["fixer_error"] = (
                "No Terraform code was provided."
            )

            return state

        # ==============================================================
        # 5. NORMALIZE FINDINGS
        # ==============================================================

        if not isinstance(
                findings,
                list,
        ):

            findings = []

        # ==============================================================
        # 6. SELECT VALID FINDINGS
        # ==============================================================

        valid_findings = []

        for index, finding in enumerate(
                findings,
                start=1,
        ):

            if not isinstance(
                    finding,
                    dict,
            ):

                logger.warning(
                    "Ignoring non-dict finding #%d.",
                    index,
                )

                continue

            terraform_location = (
                    finding.get(
                        "terraform_location"
                    )
                    or
                    finding.get(
                        "terraform_path"
                    )
            )

            if not isinstance(
                    terraform_location,
                    str,
            ):

                logger.warning(
                    "Ignoring finding #%d: "
                    "missing Terraform location.",
                    index,
                )

                continue

            if not terraform_location.strip():

                logger.warning(
                    "Ignoring finding #%d: "
                    "empty Terraform location.",
                    index,
                )

                continue

            # ----------------------------------------------------------
            # Evidence is mandatory for a Validator finding.
            # ----------------------------------------------------------

            evidence_quote = finding.get(
                "evidence_quote"
            )

            evidence_document = finding.get(
                "evidence_document"
            )

            if not evidence_quote:

                logger.warning(
                    "Ignoring finding #%d: "
                    "missing evidence quote.",
                    index,
                )

                continue

            if evidence_document is None:

                logger.warning(
                    "Ignoring finding #%d: "
                    "missing evidence document.",
                    index,
                )

                continue

            valid_findings.append(
                finding
            )

        logger.info(
            "Valid findings for Fixer=%d",
            len(valid_findings),
        )

        # ==============================================================
        # 7. NO VALID FINDINGS
        # ==============================================================

        if not valid_findings:

            logger.warning(
                "Fix requested but no valid Validator finding "
                "is available for remediation."
            )

            state["fixed_terraform"] = (
                terraform_code
            )

            state["fix_success"] = False

            state["fix_summary"] = (
                "No valid Terraform finding was available "
                "for remediation."
            )

            state["fixer_error"] = (
                "No valid Terraform finding was available "
                "for remediation."
            )

            return state

        # ==============================================================
        # 8. NORMALIZE INFRASTRUCTURE
        # ==============================================================

        if not isinstance(
                infrastructure,
                dict,
        ):

            logger.warning(
                "Invalid infrastructure supplied to Fixer."
            )

            infrastructure = {}

        # ==============================================================
        # 9. NORMALIZE DOCUMENTS
        # ==============================================================

        if not isinstance(
                documents,
                list,
        ):

            documents = []

        # ==============================================================
        # 10. NORMALIZE RECOMMENDATIONS
        # ==============================================================

        if not isinstance(
                recommendations,
                list,
        ):

            recommendations = []

        # ==============================================================
        # 11. CALL FIXER SERVICE
        # ==============================================================

        logger.info(
            "========== CALLING FIXER SERVICE =========="
        )

        logger.info(
            "Terraform length=%d",
            len(terraform_code),
        )

        logger.info(
            "Valid findings=%d",
            len(valid_findings),
        )

        logger.info(
            "Documents=%d",
            len(documents),
        )

        logger.info(
            "Recommendations=%d",
            len(recommendations),
        )

        result = await fixer_service.fix(
            terraform_code=terraform_code,
            findings=valid_findings,
            infrastructure=infrastructure,
            documents=documents,
            recommendations=recommendations,
        )

        # ==============================================================
        # 12. VALIDATE FIXER SERVICE RESULT
        # ==============================================================

        if not isinstance(
                result,
                dict,
        ):

            raise RuntimeError(
                "FixerService returned an invalid result."
            )

        # ==============================================================
        # 13. READ RESULT
        # ==============================================================

        success = bool(
            result.get(
                "success",
                False,
            )
        )

        fixed_terraform = result.get(
            "fixed_terraform"
        )

        changes = result.get(
            "changes",
            [],
        )

        rejected_changes = result.get(
            "rejected_changes",
            [],
        )

        fix_summary = result.get(
            "fix_summary",
            result.get(
                "summary",
                "",
            ),
        )

        service_error = result.get(
            "error"
        )

        # ==============================================================
        # 14. NORMALIZE RESULT TYPES
        # ==============================================================

        if not isinstance(
                changes,
                list,
        ):

            changes = []

        if not isinstance(
                rejected_changes,
                list,
        ):

            rejected_changes = []

        if not isinstance(
                fix_summary,
                str,
        ):

            fix_summary = str(
                fix_summary
            )

        if service_error is not None:

            service_error = str(
                service_error
            ).strip()

        # ==============================================================
        # 15. VALIDATE FIXED TERRAFORM
        # ==============================================================

        if (
                not isinstance(
                    fixed_terraform,
                    str,
                )
                or
                not fixed_terraform.strip()
        ):

            logger.warning(
                "FixerService did not return valid Terraform."
            )

            fixed_terraform = (
                terraform_code
            )

            success = False

            if not service_error:

                service_error = (
                    "Fixer did not return valid Terraform."
                )

        # ==============================================================
        # 16. SAFETY CHECK
        #
        # If Fixer says success=True but made no changes,
        # keep original Terraform and mark the operation explicitly.
        # ==============================================================

        if (
                success
                and
                not changes
        ):

            # This is not necessarily an error:
            # the Fixer may determine that no safe modification
            # is possible.

            logger.info(
                "Fixer reported success with no accepted changes."
            )

        # ==============================================================
        # 17. STORE FIXER RESULT
        # ==============================================================

        state["fixed_terraform"] = (
            fixed_terraform
        )

        state["fix_success"] = (
            success
        )

        state["fix_summary"] = (
            fix_summary
        )

        state["changes"] = (
            changes
        )

        state["rejected_changes"] = (
            rejected_changes
        )

        state["fixer_error"] = (
            service_error
        )

        # ==============================================================
        # IMPORTANT
        #
        # DO NOT DO:
        #
        # state["error"] = service_error
        #
        # because Validator and Fixer have different responsibilities.
        #
        # Validator:
        #     state["error"]
        #
        # Fixer:
        #     state["fixer_error"]
        #
        # =============================================================

        logger.info(
            "========== FIXER RESULT =========="
        )

        logger.info(
            "Success=%s",
            state["fix_success"],
        )

        logger.info(
            "Changes=%d",
            len(
                state["changes"]
            ),
        )

        logger.info(
            "Rejected changes=%d",
            len(
                state["rejected_changes"]
            ),
        )

        logger.info(
            "Fix summary=%s",
            state["fix_summary"],
        )

        if state["fixer_error"]:

            logger.warning(
                "Fixer error=%s",
                state["fixer_error"],
            )

        return state

    except Exception as exc:

        logger.exception(
            "Fixer node failed."
        )

        # Keep original Terraform.
        state["fixed_terraform"] = (
            state.get(
                "terraform_code"
            )
        )

        state["fix_success"] = False

        state["changes"] = []

        state["rejected_changes"] = []

        state["fix_summary"] = (
            "Terraform fixer failed."
        )

        state["fixer_error"] = str(
            exc
        )

        # IMPORTANT:
        # Keep Validator's state["error"] untouched.
        return state