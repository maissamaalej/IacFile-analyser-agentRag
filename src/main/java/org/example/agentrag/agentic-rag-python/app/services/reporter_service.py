import json
import logging
import re
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


class ReporterService:
    """
    Final response generator.

    Two modes:

    1. IaC Analysis
       -> Formats the result produced by ValidatorService.

    2. RAG Question
       -> Generates a structured answer using retrieved Azure documents.

    ReporterService NEVER:
        - validates Terraform
        - creates findings
        - modifies findings
        - recalculates the score
        - invents Azure rules
        - converts Validation Error into Compliant
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
            reranked_documents: Optional[List[Dict[str, Any]]] = None,
            retrieved_documents: Optional[List[Dict[str, Any]]] = None,
    ) -> str:

        try:

            # ----------------------------------------------------------
            # NORMALIZE INPUTS
            # ----------------------------------------------------------

            if not isinstance(findings, list):
                findings = []

            if not isinstance(recommendations, list):
                recommendations = []

            if not isinstance(changes, list):
                changes = []

            if score is None:
                score = 0

            try:
                score = int(score)
            except (TypeError, ValueError):
                score = 0

            score = max(0, min(100, score))

            if not isinstance(status, str):
                status = str(status)

            status = status.strip()

            if status not in {
                "Compliant",
                "Non-Compliant",
                "Validation Error",
            }:
                status = "Validation Error"

            # ----------------------------------------------------------
            # IAC ANALYSIS
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

            return f"Report generation error: {exc}"

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

        if not isinstance(findings, list):
            findings = []

        if not isinstance(recommendations, list):
            recommendations = []

        if not isinstance(changes, list):
            changes = []

        if score is None:
            score = 0

        try:
            score = int(score)
        except (TypeError, ValueError):
            score = 0

        score = max(0, min(100, score))

        if not isinstance(status, str):
            status = str(status)

        status = status.strip()

        if status not in {
            "Compliant",
            "Non-Compliant",
            "Validation Error",
        }:
            status = "Validation Error"

        report: List[str] = []

        report.append(
            "# Azure Infrastructure Validation Report\n\n"
        )

        report.append(
            "## Infrastructure Score\n\n"
        )

        report.append(
            f"**Score : {score}/100**\n\n"
        )

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
                    or validation_summary
                    or (
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

                    if not isinstance(change, dict):
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

            final_report = "".join(report)

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

        # ==============================================================
        # NORMAL CONCLUSIVE RESULT
        # ==============================================================

        report.append(
            "## Findings\n\n"
        )

        if status == "Compliant" and not findings:

            report.append(
                "✅ No supported security or architecture issue "
                "was identified from the retrieved Azure evidence.\n\n"
            )

        elif status == "Non-Compliant" and not findings:

            logger.error(
                "Reporter received Non-Compliant with zero findings."
            )

            report.append(
                "⚠️ Validation result is inconsistent: "
                "status is Non-Compliant but no validated findings "
                "were provided.\n\n"
            )

        else:

            finding_number = 0

            for finding in findings:

                if not isinstance(finding, dict):
                    continue

                finding_number += 1

                report.append(
                    f"### Finding {finding_number}\n\n"
                )

                report.append(
                    "**Resource**\n"
                    f"{finding.get('resource', 'Unknown')}\n\n"
                )

                report.append(
                    "**Resource Name**\n"
                    f"{finding.get('resource_name', 'Unknown')}\n\n"
                )

                report.append(
                    "**Severity**\n"
                    f"{finding.get('severity', 'Unknown')}\n\n"
                )

                report.append(
                    "**Status**\n"
                    f"{finding.get('status', 'Failed')}\n\n"
                )

                report.append(
                    "**Rule**\n"
                    f"{finding.get('rule', '')}\n\n"
                )

                observed_value = finding.get(
                    "observed_value"
                )

                if observed_value is not None:

                    report.append(
                        "**Observed Value**\n"
                    )

                    if isinstance(
                            observed_value,
                            (dict, list),
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

                report.append(
                    "**Problem**\n"
                    f"{finding.get('problem', '')}\n\n"
                )

                report.append(
                    "**Why it matters**\n"
                    f"{finding.get('reason', '')}\n\n"
                )

                report.append(
                    "**Recommendation**\n"
                    f"{finding.get('recommendation', '')}\n\n"
                )

                terraform_location = finding.get(
                    "terraform_location",
                    "",
                )

                if not terraform_location:

                    terraform_location = finding.get(
                        "terraform_path",
                        "",
                    )

                report.append(
                    "**Terraform Location**\n"
                    f"`{terraform_location}`\n\n"
                )

                evidence = finding.get(
                    "evidence",
                    {},
                )

                reference = finding.get(
                    "reference",
                    {},
                )

                if not isinstance(evidence, dict):
                    evidence = {}

                if not isinstance(reference, dict):
                    reference = {}

                report.append(
                    "**Azure Reference**\n\n"
                )

                title = (
                        reference.get("title")
                        or evidence.get("title")
                )

                source = (
                        reference.get("source")
                        or evidence.get("source")
                )

                page = (
                    reference.get("page")
                    if reference.get("page") is not None
                    else evidence.get("page")
                )

                quote = (
                        finding.get("evidence_quote")
                        or evidence.get("quote")
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
                        and not source
                        and page is None
                        and not quote
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

            if not isinstance(finding, dict):
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

                if not isinstance(change, dict):
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

        final_report = "".join(report)

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
            reranked_documents: Optional[List[Dict[str, Any]]],
            retrieved_documents: Optional[List[Dict[str, Any]]],
    ) -> str:

        # --------------------------------------------------------------
        # DOCUMENT SELECTION
        # --------------------------------------------------------------

        if (
                isinstance(reranked_documents, list)
                and reranked_documents
        ):

            documents = reranked_documents

        elif (
                isinstance(retrieved_documents, list)
                and retrieved_documents
        ):

            documents = retrieved_documents

        else:

            documents = []

        # --------------------------------------------------------------
        # LIMIT CONTEXT
        # --------------------------------------------------------------

        documents = documents[:5]

        if not documents:

            return (
                "No Azure documentation was found "
                "for this question."
            )

        # --------------------------------------------------------------
        # BUILD CONTEXT
        # --------------------------------------------------------------

        context_parts: List[str] = []

        for index, document in enumerate(
                documents,
                start=1,
        ):

            if not isinstance(document, dict):
                continue

            content = str(
                document.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            title = str(
                document.get(
                    "title",
                    "",
                )
            ).strip()

            source = str(
                document.get(
                    "source",
                    "",
                )
            ).strip()

            page = str(
                document.get(
                    "page",
                    "",
                )
            ).strip()

            context_parts.append(
                "\n".join(
                    [
                        f"DOCUMENT {index}",
                        "",
                        f"Title: {title}",
                        f"Source: {source}",
                        f"Page: {page}",
                        "",
                        "Content:",
                        content,
                        "",
                        f"END DOCUMENT {index}",
                    ]
                )
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

        system_prompt = """
You are an Azure Cloud Architect.

Your task is to answer the user's question using ONLY the
provided Azure documentation.

The retrieved documentation is the source of truth.

Do not invent:
- Azure services
- Azure features
- Terraform properties
- configuration values
- recommendations
- facts
- numbers
- commands
- URLs
- implementation details

If the documentation does not contain enough information,
say so clearly.

============================================================
ANSWER STRUCTURE
============================================================

Adapt the structure to the user's question.

For a general "What is..." question:

Short explanation.

## Key Points

- Point
- Point
- Point

## Benefits

- Benefit
- Benefit

## Summary

Short conclusion.

For a "How to..." question:

# Title

Give a short introduction explaining the goal.

## 1. First Main Step

Explain the first step.

- Action
- Action
- Action

## 2. Second Main Step

Explain the second step.

- Action
- Action
- Action

## 3. Third Main Step

Explain the third step.

- Action
- Action

## Azure Tools

### Tool 1

Explain the role of the tool.

### Tool 2

Explain the role of the tool.

## Best Practices

- Practice
- Practice
- Practice

## Summary

Give a short summary of the main recommendations.

============================================================
STRICT MARKDOWN RULES
============================================================

1. Always begin with exactly one H1 title.

2. Every heading MUST be on its own line.

3. Use:
   # for the main title
   ## for major sections
   ### for subsections

4. Always insert a blank line before and after headings.

5. Every bullet MUST be on its own line.

6. Every numbered list item MUST be on its own line.

7. Never put multiple numbered items on one line.

8. Never put multiple bullet points on one line.

9. Never concatenate headings with text.

10. Never concatenate words.

11. Use normal spaces between words.

12. Do not create extremely long paragraphs.

13. Prefer short paragraphs of 1-3 sentences.

14. Group related information under the same section.

15. Use numbered sections when explaining a process.

16. Use bullet points for recommendations and lists.

17. Use ### subsections when several Azure services/tools need
    to be explained separately.

18. Do not repeat the question.

19. Do not mention "retrieved documents", "RAG", "chunks",
    "reranking", "context", or internal processing.

20. Do not add a References section unless the supplied
    documentation explicitly provides useful source information.

21. Do not use a table unless a table is clearly useful.

22. Keep the answer concise but sufficiently informative.

============================================================
IMPORTANT
============================================================

The final response must look like a professional Azure
documentation answer.

Do NOT copy the retrieved documentation as one large block.

Instead, synthesize the information into a clear structure
while preserving only information supported by the documents.
"""

        user_prompt = (
            f"User question:\n"
            f"{prompt}\n\n"
            f"Azure documentation:\n"
            f"{context}\n\n"
            "Generate the final answer now."
        )

        try:

            response = await llm_service.generate(
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt,
                    },
                    {
                        "role": "user",
                        "content": user_prompt,
                    },
                ],
                temperature=0,
            )

        except Exception as exc:

            logger.exception(
                "RAG LLM generation failed: %s",
                exc,
            )

            return (
                "Unable to generate an Azure documentation answer."
            )

        # --------------------------------------------------------------
        # RESPONSE VALIDATION
        # --------------------------------------------------------------

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
            or ""
        ).strip()

        if not response:

            return (
                "No answer was generated."
            )

        # --------------------------------------------------------------
        # MARKDOWN NORMALIZATION
        # --------------------------------------------------------------

        response = self.format_rag_response(
            response
        )

        return response

    # ==================================================================
    # RAG MARKDOWN FORMATTER
    # ==================================================================

    def format_rag_response(
            self,
            response: str,
    ) -> str:
        """
        Normalize Markdown presentation.

        This formatter is intentionally conservative.
        It does not rewrite the semantic content.
        """

        if not response:

            return "No answer was generated."

        text = str(response)

        # --------------------------------------------------------------
        # NORMALIZE LINE ENDINGS
        # --------------------------------------------------------------

        text = text.replace(
            "\r\n",
            "\n",
        )

        text = text.replace(
            "\r",
            "\n",
        )

        # --------------------------------------------------------------
        # REMOVE TRAILING SPACES
        # --------------------------------------------------------------

        text = "\n".join(
            line.rstrip()
            for line in text.split("\n")
        )

        # --------------------------------------------------------------
        # PROTECT CODE BLOCKS
        # --------------------------------------------------------------

        code_blocks: List[str] = []

        def protect_code_block(match):

            placeholder = (
                f"@@CODE_BLOCK_{len(code_blocks)}@@"
            )

            code_blocks.append(
                match.group(0)
            )

            return f"\n{placeholder}\n"

        text = re.sub(
            r"```[\s\S]*?```",
            protect_code_block,
            text,
        )

        # --------------------------------------------------------------
        # NORMALIZE COMMON INLINE HEADINGS
        # --------------------------------------------------------------

        # Example:
        # sentence ## Section
        #
        # ->
        #
        # sentence
        #
        # ## Section

        text = re.sub(
            r"[ \t]+(#{1,6}[ \t]+)",
            r"\n\n\1",
            text,
        )

        text = re.sub(
            r"([.!?])\s+(#{1,6}[ \t]+)",
            r"\1\n\n\2",
            text,
        )

        # --------------------------------------------------------------
        # NORMALIZE NUMBERED LISTS
        # --------------------------------------------------------------

        text = re.sub(
            r"[ \t]+(\d+[.)][ \t]+)",
            r"\n\1",
            text,
        )

        text = re.sub(
            r"([.!?])\s+(\d+[.)][ \t]+)",
            r"\1\n\2",
            text,
        )

        # --------------------------------------------------------------
        # NORMALIZE BULLET LISTS
        # --------------------------------------------------------------

        text = re.sub(
            r"[ \t]+([-*+][ \t]+)",
            r"\n\1",
            text,
        )

        # --------------------------------------------------------------
        # NORMALIZE BOLD LABELS
        # --------------------------------------------------------------

        text = re.sub(
            r"[ \t]+(\*\*[^*\n]+:\*\*)",
            r"\n\n\1",
            text,
        )

        # --------------------------------------------------------------
        # KNOWN SECTION HEADINGS
        # --------------------------------------------------------------

        known_sections = [
            "Overview",
            "Key Points",
            "Key Azure Best Practices",
            "Implementation Guidance",
            "Recommended Azure Services",
            "Azure Tools",
            "Best Practices",
            "Benefits",
            "Considerations",
            "Prerequisites",
            "Configuration",
            "Summary",
            "Why it matters",
            "Description",
        ]

        for section in known_sections:

            pattern = (
                    r"[ \t]+("
                    r"#{1,6}[ \t]+"
                    + re.escape(section)
                    + r"[ \t]*)"
            )

            text = re.sub(
                pattern,
                r"\n\n\1",
                text,
                flags=re.IGNORECASE,
            )

        # --------------------------------------------------------------
        # SEPARATE HEADINGS FROM FOLLOWING CONTENT
        # --------------------------------------------------------------

        lines = text.split("\n")
        normalized_lines: List[str] = []

        for line in lines:

            stripped = line.strip()

            if re.match(
                    r"^#{1,6}[ \t]+\S+",
                    stripped,
            ):

                if (
                        normalized_lines
                        and normalized_lines[-1].strip() != ""
                ):
                    normalized_lines.append("")

                normalized_lines.append(
                    stripped
                )

                normalized_lines.append("")

            else:

                normalized_lines.append(
                    line
                )

        text = "\n".join(
            normalized_lines
        )

        # --------------------------------------------------------------
        # RESTORE CODE BLOCKS
        # --------------------------------------------------------------

        for index, code_block in enumerate(
                code_blocks,
        ):

            placeholder = (
                f"@@CODE_BLOCK_{index}@@"
            )

            text = text.replace(
                placeholder,
                code_block.strip(),
            )

        # --------------------------------------------------------------
        # CLEAN SPACES
        # --------------------------------------------------------------

        text = re.sub(
            r"[ \t]+\n",
            "\n",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        # --------------------------------------------------------------
        # ENSURE H1 EXISTS
        # --------------------------------------------------------------

        stripped = text.strip()

        if stripped and not re.match(
                r"^#\s+\S+",
                stripped,
        ):

            first_line_end = stripped.find("\n")

            if first_line_end == -1:

                title = stripped
                body = ""

            else:

                title = stripped[:first_line_end].strip()
                body = stripped[first_line_end:].strip()

            title = re.sub(
                r"^[#\s]+",
                "",
                title,
            )

            if title:

                if body:

                    stripped = (
                        f"# {title}\n\n"
                        f"{body}"
                    )

                else:

                    stripped = f"# {title}"

        # --------------------------------------------------------------
        # FINAL CLEANUP
        # --------------------------------------------------------------

        return stripped.strip()


# ======================================================================
# SINGLETON
# ======================================================================

reporter_service = ReporterService()
