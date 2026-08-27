import json
import logging
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class ReporterService:
    """
    Final response generator.

    ReporterService has two modes:

    1. IaC Analysis
       -> Formats the result already produced by ValidatorService.

    2. RAG Question
       -> Generates an answer using retrieved Azure documents.

    IMPORTANT
    ---------
    ReporterService NEVER:
        - validates Terraform
        - creates findings
        - modifies findings
        - recalculates the score
        - invents Azure rules
        - converts Validation Error into Compliant

    For IaC:
        ValidatorService is the source of truth.
    """

    # ==================================================================
    # PUBLIC ENTRY
    # ==================================================================

    async def generate_report(
            self,
            prompt: str,
            terraform_code: Optional[str],
            findings: Optional[List[Dict[str, Any]]],
            recommendations: Optional[List[Dict[str, Any]]],
            score: Optional[int],
            status: str = "Validation Error",
            validation_summary: Optional[str] = None,
            error: Optional[str] = None,
            fixed_terraform: Optional[str] = None,
            changes: Optional[List[Dict[str, Any]]] = None,
            reranked_documents: Optional[
                List[Dict[str, Any]]
            ] = None,
            retrieved_documents: Optional[
                List[Dict[str, Any]]
            ] = None,
    ) -> str:

        try:

            # ----------------------------------------------------------
            # NORMALIZE INPUTS
            # ----------------------------------------------------------

            if findings is None:
                findings = []

            if recommendations is None:
                recommendations = []

            if changes is None:
                changes = []

            if not isinstance(
                    findings,
                    list,
            ):
                findings = []

            if not isinstance(
                    recommendations,
                    list,
            ):
                recommendations = []

            if not isinstance(
                    changes,
                    list,
            ):
                changes = []

            if score is None:
                score = 0

            try:
                score = int(score)
            except (
                    TypeError,
                    ValueError,
            ):
                score = 0

            score = max(
                0,
                min(
                    100,
                    score,
                ),
            )

            if not isinstance(
                    status,
                    str,
            ):
                status = str(status)

            status = status.strip()

            if status not in {
                "Compliant",
                "Non-Compliant",
                "Validation Error",
            }:
                status = "Validation Error"

            # ----------------------------------------------------------
            # IAC
            # ----------------------------------------------------------

            if terraform_code:

                return self.generate_iac_report(
                    terraform_code=terraform_code,
                    findings=findings,
                    recommendations=recommendations,
                    score=score,
                    status=status,
                    validation_summary=validation_summary,
                    error=error,
                    fixed_terraform=fixed_terraform,
                    changes=changes,
                )

            # ----------------------------------------------------------
            # NORMAL RAG QUESTION
            # ----------------------------------------------------------

            return await self.generate_rag_report(
                prompt=prompt,
                reranked_documents=reranked_documents,
                retrieved_documents=retrieved_documents,
            )

        except Exception as exc:

            logger.exception(
                "ReporterService failed: %s",
                exc,
            )

            return (
                "Report generation error: "
                f"{exc}"
            )

    # ==================================================================
    # IAC REPORT
    # ==================================================================

    def generate_iac_report(
            self,
            terraform_code: str,
            findings: List[Dict[str, Any]],
            recommendations: List[Dict[str, Any]],
            score: Optional[int],
            status: str,
            validation_summary: Optional[str] = None,
            error: Optional[str] = None,
            fixed_terraform: Optional[str] = None,
            changes: Optional[List[Dict[str, Any]]] = None,
    ) -> str:

        # --------------------------------------------------------------
        # NORMALIZATION
        # --------------------------------------------------------------

        if not isinstance(
                findings,
                list,
        ):
            findings = []

        if not isinstance(
                recommendations,
                list,
        ):
            recommendations = []

        if not isinstance(
                changes,
                list,
        ):
            changes = []

        if score is None:
            score = 0

        try:
            score = int(score)
        except (
                TypeError,
                ValueError,
        ):
            score = 0

        score = max(
            0,
            min(
                100,
                score,
            ),
        )

        if not isinstance(
                status,
                str,
        ):
            status = str(status)

        status = status.strip()

        if status not in {
            "Compliant",
            "Non-Compliant",
            "Validation Error",
        }:
            status = "Validation Error"

        # --------------------------------------------------------------
        # REPORT
        # --------------------------------------------------------------

        report: List[str] = []

        report.append(
            "# Azure Infrastructure Validation Report\n\n"
        )

        # --------------------------------------------------------------
        # SCORE
        # --------------------------------------------------------------

        report.append(
            "## Infrastructure Score\n\n"
        )

        report.append(
            f"**Score : {score}/100**\n\n"
        )

        # --------------------------------------------------------------
        # VALIDATION STATUS
        # --------------------------------------------------------------

        report.append(
            "## Validation Status\n\n"
        )

        report.append(
            f"**Status : {status}**\n\n"
        )

        # ==============================================================
        # VALIDATION ERROR
        # ==============================================================

        if status == "Validation Error":

            report.append(
                "## Validation Error\n\n"
            )

            validation_error_message = (
                    error
                    or
                    validation_summary
                    or
                    (
                        "No definitive validation conclusion "
                        "could be produced from the available "
                        "Terraform and Azure evidence."
                    )
            )

            report.append(
                f"{validation_error_message}\n\n"
            )

            report.append(
                "## Findings\n\n"
            )

            report.append(
                "⚠️ No compliance conclusion can be made because "
                "the Terraform validation was not conclusive.\n\n"
            )

            # ----------------------------------------------------------
            # SUMMARY OF VALIDATION ERROR
            # ----------------------------------------------------------

            report.append(
                "## Summary\n\n"
            )

            report.append(
                "Validation status : Validation Error\n\n"
            )

            report.append(
                "Total findings : 0\n\n"
            )

            report.append(
                "Critical : 0\n\n"
            )

            report.append(
                "High : 0\n\n"
            )

            report.append(
                "Medium : 0\n\n"
            )

            report.append(
                "Low : 0\n\n"
            )

            if fixed_terraform:

                report.append(
                    "## Corrected Terraform\n\n"
                )

                report.append(
                    "```terraform\n"
                )

                report.append(
                    fixed_terraform.strip()
                )

                report.append(
                    "\n```\n\n"
                )

            if changes:

                report.append(
                    "## Changes Applied\n\n"
                )

                for change in changes:

                    if not isinstance(
                            change,
                            dict,
                    ):
                        continue

                    resource = str(
                        change.get(
                            "resource",
                            "",
                        )
                    ).strip()

                    description = str(
                        change.get(
                            "description",
                            "",
                        )
                    ).strip()

                    if resource:
                        report.append(
                            f"**{resource}**\n\n"
                        )

                    if description:
                        report.append(
                            f"{description}\n\n"
                        )

            final_report = "".join(
                report
            )

            logger.info(
                "========== FINAL IAC REPORT =========="
            )

            logger.info(
                "%s",
                final_report,
            )

            return final_report

        # ==============================================================
        # NORMAL CONCLUSIVE RESULT
        # ==============================================================

        report.append(
            "## Findings\n\n"
        )

        # --------------------------------------------------------------
        # COMPLIANT
        # --------------------------------------------------------------

        if status == "Compliant" and not findings:

            report.append(
                "✅ No supported security or architecture issue "
                "was identified from the retrieved Azure evidence.\n\n"
            )

        # --------------------------------------------------------------
        # SAFETY: CONCLUSIVE EMPTY NON-COMPLIANT IS INVALID
        # --------------------------------------------------------------

        elif status == "Non-Compliant" and not findings:

            logger.error(
                "Reporter received Non-Compliant with zero findings."
            )

            report.append(
                "⚠️ Validation result is inconsistent: "
                "status is Non-Compliant but no validated findings "
                "were provided.\n\n"
            )

        # --------------------------------------------------------------
        # FINDINGS
        # --------------------------------------------------------------

        else:

            finding_number = 0

            for finding in findings:

                if not isinstance(
                        finding,
                        dict,
                ):
                    continue

                finding_number += 1

                report.append(
                    f"### Finding {finding_number}\n\n"
                )

                # ------------------------------------------------------
                # RESOURCE
                # ------------------------------------------------------

                report.append(
                    "**Resource**\n"
                    f"{finding.get('resource', 'Unknown')}\n\n"
                )

                # ------------------------------------------------------
                # RESOURCE NAME
                # ------------------------------------------------------

                report.append(
                    "**Resource Name**\n"
                    f"{finding.get('resource_name', 'Unknown')}\n\n"
                )

                # ------------------------------------------------------
                # SEVERITY
                # ------------------------------------------------------

                report.append(
                    "**Severity**\n"
                    f"{finding.get('severity', 'Unknown')}\n\n"
                )

                # ------------------------------------------------------
                # STATUS
                # ------------------------------------------------------

                report.append(
                    "**Status**\n"
                    f"{finding.get('status', 'Failed')}\n\n"
                )

                # ------------------------------------------------------
                # RULE
                # ------------------------------------------------------

                report.append(
                    "**Rule**\n"
                    f"{finding.get('rule', '')}\n\n"
                )

                # ------------------------------------------------------
                # OBSERVED VALUE
                # ------------------------------------------------------

                observed_value = finding.get(
                    "observed_value"
                )

                if observed_value is not None:

                    report.append(
                        "**Observed Value**\n"
                    )

                    if isinstance(
                            observed_value,
                            (
                                    dict,
                                    list,
                            ),
                    ):

                        report.append(
                            "```json\n"
                        )

                        report.append(
                            json.dumps(
                                observed_value,
                                ensure_ascii=False,
                                indent=2,
                                default=str,
                            )
                        )

                        report.append(
                            "\n```\n\n"
                        )

                    else:

                        report.append(
                            f"`{observed_value}`\n\n"
                        )

                # ------------------------------------------------------
                # PROBLEM
                # ------------------------------------------------------

                report.append(
                    "**Problem**\n"
                    f"{finding.get('problem', '')}\n\n"
                )

                # ------------------------------------------------------
                # REASON
                # ------------------------------------------------------

                report.append(
                    "**Why it matters**\n"
                    f"{finding.get('reason', '')}\n\n"
                )

                # ------------------------------------------------------
                # RECOMMENDATION
                # ------------------------------------------------------

                report.append(
                    "**Recommendation**\n"
                    f"{finding.get('recommendation', '')}\n\n"
                )

                # ------------------------------------------------------
                # TERRAFORM LOCATION
                # ------------------------------------------------------

                terraform_location = (
                    finding.get(
                        "terraform_location",
                        "",
                    )
                )

                if not terraform_location:

                    terraform_location = (
                        finding.get(
                            "terraform_path",
                            "",
                        )
                    )

                report.append(
                    "**Terraform Location**\n"
                    f"`{terraform_location}`\n\n"
                )

                # ------------------------------------------------------
                # AZURE EVIDENCE
                # ------------------------------------------------------

                evidence = finding.get(
                    "evidence",
                    {},
                )

                reference = finding.get(
                    "reference",
                    {},
                )

                if not isinstance(
                        evidence,
                        dict,
                ):
                    evidence = {}

                if not isinstance(
                        reference,
                        dict,
                ):
                    reference = {}

                report.append(
                    "**Azure Reference**\n\n"
                )

                title = (
                        reference.get("title")
                        or
                        evidence.get("title")
                )

                source = (
                        reference.get("source")
                        or
                        evidence.get("source")
                )

                page = (
                    reference.get("page")
                    if reference.get("page") is not None
                    else evidence.get("page")
                )

                quote = (
                        finding.get("evidence_quote")
                        or
                        evidence.get("quote")
                )

                if title:

                    report.append(
                        f"Title : {title}\n\n"
                    )

                if source:

                    report.append(
                        f"Source : {source}\n\n"
                    )

                if page is not None:

                    report.append(
                        f"Page : {page}\n\n"
                    )

                if quote:

                    report.append(
                        f"Evidence : {quote}\n\n"
                    )

                if (
                        not title
                        and
                        not source
                        and
                        page is None
                        and
                        not quote
                ):

                    report.append(
                        "No reference metadata available.\n\n"
                    )

                report.append(
                    "---\n\n"
                )

        # ==============================================================
        # SUMMARY
        # ==============================================================

        critical = 0
        high = 0
        medium = 0
        low = 0

        for finding in findings:

            if not isinstance(
                    finding,
                    dict,
            ):
                continue

            severity = str(
                finding.get(
                    "severity",
                    "",
                )
            ).strip().lower()

            if severity == "critical":
                critical += 1

            elif severity == "high":
                high += 1

            elif severity == "medium":
                medium += 1

            elif severity == "low":
                low += 1

        report.append(
            "## Summary\n\n"
        )

        report.append(
            f"Validation status : {status}\n\n"
        )

        report.append(
            f"Total findings : {len(findings)}\n\n"
        )

        report.append(
            f"Critical : {critical}\n\n"
        )

        report.append(
            f"High : {high}\n\n"
        )

        report.append(
            f"Medium : {medium}\n\n"
        )

        report.append(
            f"Low : {low}\n\n"
        )

        if validation_summary:

            report.append(
                f"{validation_summary}\n\n"
            )

        # ==============================================================
        # CORRECTED TERRAFORM
        # ==============================================================

        if fixed_terraform:

            report.append(
                "## Corrected Terraform\n\n"
            )

            report.append(
                "```terraform\n"
            )

            report.append(
                fixed_terraform.strip()
            )

            report.append(
                "\n```\n\n"
            )

        # ==============================================================
        # CHANGES
        # ==============================================================

        if changes:

            report.append(
                "## Changes Applied\n\n"
            )

            for change in changes:

                if not isinstance(
                        change,
                        dict,
                ):
                    continue

                resource = str(
                    change.get(
                        "resource",
                        "",
                    )
                ).strip()

                description = str(
                    change.get(
                        "description",
                        "",
                    )
                ).strip()

                if resource:

                    report.append(
                        f"**{resource}**\n\n"
                    )

                if description:

                    report.append(
                        f"{description}\n\n"
                    )

        # ==============================================================
        # FINAL
        # ==============================================================

        final_report = "".join(
            report
        )

        logger.info(
            "========== FINAL IAC REPORT =========="
        )

        logger.info(
            "%s",
            final_report,
        )

        logger.info(
            "======================================"
        )

        return final_report

    # ==================================================================
    # RAG REPORT
    # ==================================================================

    async def generate_rag_report(
            self,
            prompt: str,
            reranked_documents: Optional[
                List[Dict[str, Any]]
            ],
            retrieved_documents: Optional[
                List[Dict[str, Any]]
            ],
    ) -> str:

        # --------------------------------------------------------------
        # DOCUMENT SELECTION
        # --------------------------------------------------------------

        if (
                isinstance(
                    reranked_documents,
                    list,
                )
                and
                reranked_documents
        ):

            documents = reranked_documents

        elif (
                isinstance(
                    retrieved_documents,
                    list,
                )
                and
                retrieved_documents
        ):

            documents = retrieved_documents

        else:

            documents = []

        documents = documents[:5]

        if not documents:

            return (
                "No Azure documentation was found "
                "for this question."
            )

        # --------------------------------------------------------------
        # CONTEXT
        # --------------------------------------------------------------

        context_parts = []

        for index, document in enumerate(
                documents,
                start=1,
        ):

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

            context_parts.append(
                f"""
DOCUMENT {index}

Title:
{document.get("title", "")}

Source:
{document.get("source", "")}

Page:
{document.get("page", "")}

Content:
{content}

END DOCUMENT {index}
"""
            )

        if not context_parts:

            return (
                "No usable Azure documentation was found."
            )

        context = "\n\n".join(
            context_parts
        )

        # --------------------------------------------------------------
        # LLM
        # --------------------------------------------------------------

        from app.services.llm_service import llm_service

        response = await llm_service.generate(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an Azure Cloud Architect. "
                        "Answer ONLY using the supplied Azure "
                        "documentation. "
                        "Do not invent information. "
                        "Return clean Markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Question:\n{prompt}\n\n"
                        f"Azure Documentation:\n{context}\n\n"
                        "Answer only from the supplied documents."
                    ),
                },
            ],
            temperature=0,
        )

        if response is None:

            return (
                "No answer was generated."
            )

        if hasattr(
                response,
                "content",
        ):

            response = response.content

        response = str(
            response
        ).strip()

        if not response:

            return (
                "No answer was generated."
            )

        return response


# ======================================================================
# SINGLETON
# ======================================================================

reporter_service = ReporterService()