import logging
from typing import Any, Dict, List

from app.graph.state import AgentState
from app.services.reporter_service import reporter_service


logger = logging.getLogger(__name__)


async def reporter_node(
        state: AgentState,
) -> Dict[str, Any]:

    logger.info(
        "========== REPORTER NODE =========="
    )

    if not isinstance(
            state,
            dict,
    ):
        return {
            "messages": [
                {
                    "role": "assistant",
                    "content": (
                        "Unable to generate the validation report."
                    ),
                }
            ]
        }

    # ==============================================================
    # READ STATE
    # ==============================================================

    validation_status = str(
        state.get(
            "validation_status",
            state.get(
                "overall_status",
                state.get(
                    "status",
                    "Validation Error",
                ),
            ),
        )
    ).strip()

    findings = state.get(
        "findings",
        [],
    )

    if not isinstance(
            findings,
            list,
    ):
        findings = []

    recommendations = state.get(
        "recommendations",
        [],
    )

    if not isinstance(
            recommendations,
            list,
    ):
        recommendations = []

    score = state.get(
        "score",
        0,
    )

    try:
        score = int(score)
    except (
            TypeError,
            ValueError,
    ):
        score = 0

    validation_summary = str(
        state.get(
            "validation_summary",
            "",
        )
        or ""
    ).strip()

    error = str(
        state.get(
            "error",
            "",
        )
        or ""
    ).strip()

    # ==============================================================
    # GENERATE REPORT
    # ==============================================================

    answer = ""

    try:

        terraform_code = state.get(
            "terraform_code",
            "",
        )

        # ----------------------------------------------------------
        # IMPORTANT:
        # Use the method that actually exists in ReporterService.
        # ----------------------------------------------------------

        result =  reporter_service.generate_iac_report(
            terraform_code=terraform_code,
            findings=findings,
            recommendations=recommendations,
            score=score,
            status=validation_status,
            validation_summary=validation_summary,
        )

        if isinstance(
                result,
                dict,
        ):

            answer = (
                    result.get(
                        "answer",
                        "",
                    )
                    or
                    result.get(
                        "report",
                        "",
                    )
                    or
                    result.get(
                        "content",
                        "",
                    )
                    or
                    ""
            )

        else:

            answer = str(
                result
                or
                ""
            )

    except Exception as exc:

        logger.exception(
            "ReporterService failed: %s",
            exc,
        )

    # ==============================================================
    # FALLBACK
    # ==============================================================

    if not answer.strip():

        answer = _build_fallback_report(
            validation_status=validation_status,
            score=score,
            findings=findings,
            recommendations=recommendations,
            validation_summary=validation_summary,
            error=error,
        )

    # ==============================================================
    # LANGGRAPH MESSAGE
    # ==============================================================

    assistant_message = {
        "role": "assistant",
        "content": answer,
    }

    logger.info(
        "Reporter answer length=%d",
        len(answer),
    )

    return {
        "messages": [
            assistant_message
        ],
        "answer": answer,
        "final_answer": answer,

        "validation_status": validation_status,
        "overall_status": validation_status,
        "status": validation_status,

        "score": score,
        "findings": findings,
        "recommendations": recommendations,
        "validation_summary": validation_summary,

        "report_generated": True,
    }


def _build_fallback_report(
        validation_status: str,
        score: int,
        findings: List[Dict[str, Any]],
        recommendations: List[Dict[str, Any]],
        validation_summary: str,
        error: str,
) -> str:

    lines = []

    lines.append(
        "# Azure Infrastructure Validation Report"
    )

    lines.append("")

    lines.append(
        "## Infrastructure Score"
    )

    lines.append("")

    lines.append(
        f"**Score : {score}/100**"
    )

    lines.append("")

    lines.append(
        "## Validation Status"
    )

    lines.append("")

    lines.append(
        f"**Status : {validation_status}**"
    )

    lines.append("")

    if validation_status == "Validation Error":

        lines.append(
            "## Validation Error"
        )

        lines.append("")

        lines.append(
            error
            or
            validation_summary
            or
            "Infrastructure validation could not be completed."
        )

        lines.append("")

    elif findings:

        lines.append(
            "## Findings"
        )

        lines.append("")

        for index, finding in enumerate(
                findings,
                start=1,
        ):

            if not isinstance(
                    finding,
                    dict,
            ):
                continue

            lines.append(
                f"### Finding {index}"
            )

            lines.append("")

            lines.append(
                f"**Resource**  \n"
                f"{finding.get('resource', '')}"
            )

            lines.append("")

            lines.append(
                f"**Resource Name**  \n"
                f"{finding.get('resource_name', '')}"
            )

            lines.append("")

            lines.append(
                f"**Severity**  \n"
                f"{finding.get('severity', '')}"
            )

            lines.append("")

            lines.append(
                f"**Status**  \n"
                f"{finding.get('status', 'Failed')}"
            )

            lines.append("")

            lines.append(
                f"**Rule**  \n"
                f"{finding.get('rule', '')}"
            )

            lines.append("")

            lines.append(
                f"**Observed Value**  \n"
                f"`{finding.get('observed_value', '')}`"
            )

            lines.append("")

            lines.append(
                f"**Problem**  \n"
                f"{finding.get('problem', '')}"
            )

            lines.append("")

            lines.append(
                f"**Why it matters**  \n"
                f"{finding.get('reason', '')}"
            )

            lines.append("")

            lines.append(
                f"**Recommendation**  \n"
                f"{finding.get('recommendation', '')}"
            )

            lines.append("")

            location = (
                    finding.get(
                        "terraform_location"
                    )
                    or
                    finding.get(
                        "terraform_path",
                        "",
                    )
            )

            lines.append(
                f"**Terraform Location**  \n"
                f"`{location}`"
            )

            lines.append("")

            lines.append(
                f"**Evidence**  \n"
                f"{finding.get('evidence_quote', '')}"
            )

            lines.append("")

            reference = finding.get(
                "reference",
                {},
            )

            if isinstance(
                    reference,
                    dict,
            ):

                title = reference.get(
                    "title"
                )

                source = reference.get(
                    "source"
                )

                page = reference.get(
                    "page"
                )

                if title or source or page:

                    lines.append(
                        "**Azure Reference**"
                    )

                    if title:
                        lines.append(
                            f"Title : {title}"
                        )

                    if source:
                        lines.append(
                            f"Source : {source}"
                        )

                    if page is not None:
                        lines.append(
                            f"Page : {page}"
                        )

                    lines.append("")

            lines.append(
                "---"
            )

            lines.append("")

    else:

        lines.append(
            "## Findings"
        )

        lines.append("")

        lines.append(
            "No supported compliance findings were confirmed."
        )

        lines.append("")

    lines.append(
        "## Summary"
    )

    lines.append("")

    lines.append(
        f"Validation status : {validation_status}"
    )

    lines.append("")

    lines.append(
        f"Total findings : {len(findings)}"
    )

    lines.append("")

    critical = sum(
        1
        for finding in findings
        if isinstance(finding, dict)
        and str(
            finding.get(
                "severity",
                "",
            )
        ).lower() == "critical"
    )

    high = sum(
        1
        for finding in findings
        if isinstance(finding, dict)
        and str(
            finding.get(
                "severity",
                "",
            )
        ).lower() == "high"
    )

    medium = sum(
        1
        for finding in findings
        if isinstance(finding, dict)
        and str(
            finding.get(
                "severity",
                "",
            )
        ).lower() == "medium"
    )

    low = sum(
        1
        for finding in findings
        if isinstance(finding, dict)
        and str(
            finding.get(
                "severity",
                "",
            )
        ).lower() == "low"
    )

    lines.append(
        f"Critical : {critical}"
    )

    lines.append("")

    lines.append(
        f"High : {high}"
    )

    lines.append("")

    lines.append(
        f"Medium : {medium}"
    )

    lines.append("")

    lines.append(
        f"Low : {low}"
    )

    lines.append("")

    lines.append(
        validation_summary
        or
        "Infrastructure validation completed."
    )

    return "\n".join(
        lines
    )