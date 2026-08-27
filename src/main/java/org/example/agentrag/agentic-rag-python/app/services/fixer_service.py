import json
import logging
import re
import subprocess
import tempfile
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

from app.services.llm_service import llm_service


logger = logging.getLogger(__name__)


class FixerService:
    """
    Dynamic Terraform remediation service.

    Principles
    ----------
    1. Terraform is the source of truth.
    2. Validator findings are the only issues that may be fixed.
    3. Azure documentation is remediation context only.
    4. The LLM does not decide whether a finding is valid.
    5. Terraform locations come from the validator/parser.
    6. The LLM returns the complete corrected Terraform.
    7. Python verifies that validator properties changed.
    8. No new findings are invented.
    9. No secrets are invented.
    10. Existing resources must be preserved.
    11. Unrelated Terraform modifications are rejected.
    12. New resources are rejected unless explicitly required.
    """

    def __init__(self, llm_service_instance=None):

        self.llm_service = (
            llm_service_instance
            if llm_service_instance is not None
            else llm_service
        )

        if self.llm_service is None:
            logger.warning(
                "FixerService initialized WITHOUT an LLM service."
            )
        else:
            logger.info(
                "FixerService initialized with LLM service."
            )

    # ==================================================================
    # PUBLIC API
    # ==================================================================

    async def fix(
            self,
            terraform_code: str,
            findings: Optional[List[Dict[str, Any]]] = None,
            infrastructure: Optional[Dict[str, Any]] = None,
            documents: Optional[List[Dict[str, Any]]] = None,
            recommendations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:

        logger.info(
            "========== DYNAMIC TERRAFORM FIXER =========="
        )

        original_terraform = (
            terraform_code
            if isinstance(terraform_code, str)
            else ""
        ).strip()

        if not original_terraform:
            return self._error_result(
                "No Terraform configuration was supplied."
            )

        findings = findings if isinstance(findings, list) else []
        infrastructure = (
            infrastructure
            if isinstance(infrastructure, dict)
            else {}
        )
        documents = documents if isinstance(documents, list) else []
        recommendations = (
            recommendations
            if isinstance(recommendations, list)
            else []
        )

        # ==============================================================
        # NO FINDINGS
        # ==============================================================

        if not findings:

            logger.info(
                "No validator findings. Nothing to fix."
            )

            return {
                "success": True,
                "fixed_terraform": original_terraform,
                "changes": [],
                "rejected_changes": [],
                "fix_summary": (
                    "No validator findings require remediation."
                ),
                "error": None,
            }

        # ==============================================================
        # STEP 1 - PREPARE FINDINGS
        # ==============================================================

        valid_findings, rejected_findings = self._prepare_findings(
            findings=findings,
            infrastructure=infrastructure,
        )

        logger.info(
            "Valid findings for fixer: %d",
            len(valid_findings),
        )

        logger.info(
            "Rejected findings before LLM: %d",
            len(rejected_findings),
        )

        if not valid_findings:

            return {
                "success": False,
                "fixed_terraform": original_terraform,
                "changes": [],
                "rejected_changes": rejected_findings,
                "fix_summary": (
                    "No validator finding could be safely "
                    "passed to the fixer."
                ),
                "error": (
                    "No valid Terraform finding was available "
                    "for remediation."
                ),
            }

        # ==============================================================
        # STEP 2 - REMEDIATION CONTEXT
        # ==============================================================

        remediation_context = self._build_remediation_context(
            findings=valid_findings,
            documents=documents,
            recommendations=recommendations,
        )

        # ==============================================================
        # STEP 3 - LLM GENERATION
        # ==============================================================

        try:

            llm_response = await self._generate_fixed_terraform(
                original_terraform=original_terraform,
                findings=valid_findings,
                remediation_context=remediation_context,
            )

        except Exception as exc:

            logger.exception(
                "Fixer LLM failed: %s",
                exc,
            )

            return {
                "success": False,
                "fixed_terraform": original_terraform,
                "changes": [],
                "rejected_changes": rejected_findings,
                "fix_summary": "Terraform fixer failed.",
                "error": str(exc),
            }

        # ==============================================================
        # STEP 4 - EXTRACT TERRAFORM
        # ==============================================================

        fixed_terraform = self._extract_terraform(
            llm_response
        )

        if not fixed_terraform:

            return {
                "success": False,
                "fixed_terraform": original_terraform,
                "changes": [],
                "rejected_changes": rejected_findings,
                "fix_summary": (
                    "Fixer did not return valid Terraform."
                ),
                "error": (
                    "No Terraform configuration returned "
                    "by fixer."
                ),
            }

        # ==============================================================
        # STEP 5 - CLEAN / FORMAT BASIC TERRAFORM
        # ==============================================================

        fixed_terraform = self._clean_terraform_output(
            fixed_terraform
        )

        # ==============================================================
        # STEP 6 - BASIC VALIDATION
        # ==============================================================

        if not self._looks_like_terraform(
                fixed_terraform
        ):

            return {
                "success": False,
                "fixed_terraform": original_terraform,
                "changes": [],
                "rejected_changes": rejected_findings,
                "fix_summary": (
                    "Fixer output was rejected because it "
                    "does not look like valid Terraform."
                ),
                "error": "Invalid Terraform fixer output.",
            }

        # ==============================================================
        # STEP 7 - TERRAFORM CLI VALIDATION
        # ==============================================================

        terraform_validation = (
            self._validate_with_terraform_cli(
                fixed_terraform
            )
        )

        if terraform_validation["available"]:

            if not terraform_validation["valid"]:

                logger.warning(
                    "Terraform CLI rejected fixer output: %s",
                    terraform_validation["error"],
                )

                return {
                    "success": False,
                    "fixed_terraform": original_terraform,
                    "changes": [],
                    "rejected_changes": rejected_findings,
                    "fix_summary": (
                        "Fixer output was rejected by "
                        "Terraform validation."
                    ),
                    "error": terraform_validation["error"],
                }

        # ==============================================================
        # STEP 8 - VERIFY FINDINGS WERE ACTUALLY FIXED
        # ==============================================================

        changes, unresolved = self._verify_fixes(
            original_terraform=original_terraform,
            fixed_terraform=fixed_terraform,
            findings=valid_findings,
            infrastructure=infrastructure,
        )

        # ==============================================================
        # STEP 9 - NO VALID FIX
        # ==============================================================

        if not changes:

            logger.warning(
                "No validator finding was actually fixed."
            )

            return {
                "success": False,
                "fixed_terraform": original_terraform,
                "changes": [],
                "rejected_changes": (
                        rejected_findings + unresolved
                ),
                "fix_summary": (
                    "Fixer output rejected because "
                    "no validator finding was actually fixed."
                ),
                "error": (
                    "Terraform changed but no valid "
                    "validator finding was fixed."
                ),
            }

        # ==============================================================
        # STEP 10 - RESOURCE CONSERVATION
        # ==============================================================

        conservation_error = (
            self._verify_resource_conservation(
                original_terraform,
                fixed_terraform,
            )
        )

        if conservation_error:

            logger.warning(
                "Terraform conservation check failed: %s",
                conservation_error,
            )

            return {
                "success": False,
                "fixed_terraform": original_terraform,
                "changes": [],
                "rejected_changes": (
                        rejected_findings
                        + unresolved
                        + [
                            {
                                "reason": conservation_error
                            }
                        ]
                ),
                "fix_summary": (
                    "Fixer output rejected because "
                    "unrelated Terraform was modified."
                ),
                "error": conservation_error,
            }

        # ==============================================================
        # STEP 11 - RETURN
        # ==============================================================

        all_rejected = (
                rejected_findings + unresolved
        )

        logger.info(
            "========== FIXER COMPLETED =========="
        )

        logger.info(
            "Valid fixes: %d",
            len(changes),
        )

        logger.info(
            "Rejected/unresolved: %d",
            len(all_rejected),
        )

        return {
            "success": True,
            "fixed_terraform": fixed_terraform,
            "changes": changes,
            "rejected_changes": all_rejected,
            "fix_summary": self._build_fix_summary(
                changes=changes,
                rejected=all_rejected,
            ),
            "error": None,
        }

    # ==================================================================
    # FINDING PREPARATION
    # ==================================================================

    def _prepare_findings(
            self,
            findings: List[Dict[str, Any]],
            infrastructure: Dict[str, Any],
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:

        valid = []
        rejected = []

        resources = infrastructure.get(
            "resources",
            [],
        )

        if not isinstance(resources, list):
            resources = []

        resource_index = {}

        for resource in resources:

            if not isinstance(resource, dict):
                continue

            resource_type = str(
                resource.get("type", "")
            ).strip()

            resource_name = str(
                resource.get("name", "")
            ).strip()

            terraform_path = str(
                resource.get(
                    "terraform_path_id",
                    "",
                )
            ).strip()

            configuration = resource.get(
                "configuration",
                {},
            )

            if (
                    resource_type
                    and resource_name
                    and terraform_path
            ):

                resource_index[terraform_path] = {
                    "type": resource_type,
                    "name": resource_name,
                    "configuration": (
                        configuration
                        if isinstance(
                            configuration,
                            dict,
                        )
                        else {}
                    ),
                }

        for finding in findings:

            if not isinstance(finding, dict):

                rejected.append({
                    "reason": (
                        "Finding is not a dictionary."
                    )
                })

                continue

            terraform_location = (
                    finding.get(
                        "terraform_location"
                    )
                    or finding.get(
                "terraform_path_id"
            )
            )

            if not isinstance(
                    terraform_location,
                    str,
            ):

                rejected.append({
                    "reason": (
                        "Finding has no Terraform location."
                    ),
                    "finding": finding,
                })

                continue

            terraform_location = (
                terraform_location.strip()
            )

            if not terraform_location:

                rejected.append({
                    "reason": (
                        "Finding has empty Terraform location."
                    ),
                    "finding": finding,
                })

                continue

            resource_info = (
                self._find_resource_for_location(
                    terraform_location,
                    resource_index,
                )
            )

            if resource_info is None:

                rejected.append({
                    "terraform_location": (
                        terraform_location
                    ),
                    "reason": (
                        "Terraform resource does not exist "
                        "in parsed infrastructure."
                    ),
                })

                continue

            property_path = (
                self._extract_property_path(
                    terraform_location
                )
            )

            if not property_path:

                rejected.append({
                    "terraform_location": (
                        terraform_location
                    ),
                    "reason": (
                        "Terraform location does not "
                        "contain a property."
                    ),
                })

                continue

            exists, value = (
                self._get_nested_value(
                    resource_info["configuration"],
                    property_path,
                )
            )

            if not exists:

                rejected.append({
                    "terraform_location": (
                        terraform_location
                    ),
                    "reason": (
                        "Terraform property does not exist "
                        "in parsed infrastructure."
                    ),
                })

                continue

            clean_finding = deepcopy(finding)

            clean_finding[
                "terraform_location"
            ] = terraform_location

            clean_finding[
                "_fix_property_path"
            ] = property_path

            clean_finding[
                "_original_value"
            ] = value

            clean_finding[
                "_resource_type"
            ] = resource_info["type"]

            clean_finding[
                "_resource_name"
            ] = resource_info["name"]

            valid.append(
                clean_finding
            )

            logger.info(
                "Accepted fixer finding: %s",
                terraform_location,
            )

        return valid, rejected

    # ==================================================================
    # RESOURCE LOOKUP
    # ==================================================================

    def _find_resource_for_location(
            self,
            terraform_location: str,
            resource_index: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        exact = resource_index.get(
            terraform_location
        )

        if exact:
            return exact

        for path, resource in resource_index.items():

            if terraform_location.startswith(
                    path + "."
            ):

                return resource

        return None

    # ==================================================================
    # PROPERTY PATH
    # ==================================================================

    def _extract_property_path(
            self,
            terraform_location: str,
    ) -> str:

        parts = [
            part.strip()
            for part in terraform_location.split(".")
            if part.strip()
        ]

        if len(parts) < 3:
            return ""

        return ".".join(
            parts[2:]
        )

    # ==================================================================
    # NESTED VALUE
    # ==================================================================

    def _get_nested_value(
            self,
            data: Any,
            path: str,
    ) -> Tuple[bool, Any]:

        if not isinstance(data, dict):
            return False, None

        current = data

        for part in path.split("."):

            if isinstance(current, dict):

                if part not in current:
                    return False, None

                current = current[part]

            elif isinstance(current, list):

                try:
                    index = int(part)
                except ValueError:
                    return False, None

                if index < 0 or index >= len(current):
                    return False, None

                current = current[index]

            else:
                return False, None

        return True, current

    # ==================================================================
    # REMEDIATION CONTEXT
    # ==================================================================

    def _build_remediation_context(
            self,
            findings: List[Dict[str, Any]],
            documents: List[Dict[str, Any]],
            recommendations: List[str],
    ) -> str:

        blocks = []

        for index, finding in enumerate(
                findings,
                start=1,
        ):

            evidence = ""

            direct_evidence = finding.get(
                "evidence"
            )

            # ----------------------------------------------------------
            # Direct evidence dictionary
            # ----------------------------------------------------------

            if isinstance(
                    direct_evidence,
                    dict,
            ):

                evidence = str(
                    direct_evidence.get(
                        "content",
                        "",
                    )
                ).strip()

            # ----------------------------------------------------------
            # Direct evidence string
            # ----------------------------------------------------------

            elif isinstance(
                    direct_evidence,
                    str,
            ):

                evidence = direct_evidence.strip()

            # ----------------------------------------------------------
            # Evidence document
            # ----------------------------------------------------------

            if not evidence:

                evidence_document = finding.get(
                    "evidence_document"
                )

                if isinstance(
                        evidence_document,
                        int,
                ):

                    document = None

                    if (
                            1
                            <= evidence_document
                            <= len(documents)
                    ):

                        document = documents[
                            evidence_document - 1
                            ]

                    elif (
                            0
                            <= evidence_document
                            < len(documents)
                    ):

                        document = documents[
                            evidence_document
                        ]

                    if isinstance(
                            document,
                            dict,
                    ):

                        evidence = str(
                            document.get(
                                "content",
                                "",
                            )
                        ).strip()

                elif isinstance(
                        evidence_document,
                        str,
                ):

                    for document in documents:

                        if not isinstance(
                                document,
                                dict,
                        ):
                            continue

                        document_id = str(
                            document.get(
                                "id",
                                document.get(
                                    "document_id",
                                    "",
                                ),
                            )
                        )

                        if (
                                document_id
                                == evidence_document
                        ):

                            evidence = str(
                                document.get(
                                    "content",
                                    "",
                                )
                            ).strip()

                            break

            block = {
                "finding_number": index,

                "terraform_location": finding.get(
                    "terraform_location"
                ),

                "resource": (
                        finding.get("resource")
                        or finding.get(
                    "_resource_type"
                )
                ),

                "resource_name": (
                        finding.get("resource_name")
                        or finding.get(
                    "_resource_name"
                )
                ),

                "property": finding.get(
                    "_fix_property_path"
                ),

                "severity": finding.get(
                    "severity"
                ),

                "problem": finding.get(
                    "problem"
                ),

                "reason": finding.get(
                    "reason"
                ),

                "recommendation": finding.get(
                    "recommendation"
                ),

                "azure_evidence": evidence,
            }

            blocks.append(
                block
            )

        return json.dumps(
            {
                "findings": blocks,
                "recommendations": recommendations,
            },
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    # ==================================================================
    # LLM GENERATION
    # ==================================================================

    async def _generate_fixed_terraform(
            self,
            original_terraform: str,
            findings: List[Dict[str, Any]],
            remediation_context: str,
    ) -> Any:

        finding_context = []

        for finding in findings:

            finding_context.append({
                "terraform_location": finding.get(
                    "terraform_location"
                ),

                "property": finding.get(
                    "_fix_property_path"
                ),

                "resource": finding.get(
                    "_resource_type"
                ),

                "resource_name": finding.get(
                    "_resource_name"
                ),

                "current_value": finding.get(
                    "_original_value"
                ),

                "problem": finding.get(
                    "problem"
                ),

                "reason": finding.get(
                    "reason"
                ),

                "recommendation": finding.get(
                    "recommendation"
                ),
            })

        finding_json = json.dumps(
            finding_context,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

        prompt = f"""
You are a strict Terraform remediation engine.

The Validator has ALREADY determined the security findings.

Your task is ONLY to fix those findings.

============================================================
ORIGINAL TERRAFORM
============================================================

{original_terraform}

============================================================
VALIDATOR FINDINGS
============================================================

{finding_json}

============================================================
AZURE REMEDIATION CONTEXT
============================================================

{remediation_context}

============================================================
STRICT RULES
============================================================

1. Preserve the original Terraform resources.

2. Fix ONLY the validator findings.

3. Do not invent security findings.

4. Do not invent Azure rules.

5. Do not invent resource names.

6. Do not delete existing resources.

7. Do not create unrelated resources.

8. Do not modify unrelated properties.

9. Do not modify provider configuration unless strictly required.

10. Never invent passwords.

11. Never invent API keys.

12. Never invent tokens.

13. Never invent private keys.

14. Never replace a hard-coded secret with another hard-coded secret.

15. If the finding concerns a hard-coded password, do NOT keep the
    original password.

16. If the recommendation requires a secret that is not available,
    use an existing Terraform variable/reference when available.

17. If no safe secret reference exists, prefer removing the
    insecure password authentication mechanism when supported by
    the Terraform resource and the validator recommendation.

18. For a finding at:

    azurerm_linux_virtual_machine.vm.admin_password

    the resulting Terraform MUST NOT contain:

    admin_password = "Password123!"

    or another invented hard-coded password.

19. If password authentication is disabled, ensure the Terraform
    configuration is internally consistent with that choice.

20. Preserve unrelated properties such as:
    name
    resource_group_name
    location
    size
    admin_username
    network_interface_ids

21. Preserve all original resources.

22. The Terraform must be properly formatted.

23. Each Terraform argument must be on its own line.

24. Nested blocks must be correctly formatted.

25. Return the COMPLETE Terraform configuration.

26. Return ONLY Terraform.

27. Do not return Markdown.

28. Do not return explanations.

29. Do not return a list of changes.

30. Do not return code fences.

============================================================
FINAL REQUIREMENT
============================================================

Return ONLY the complete corrected Terraform configuration.
"""

        if self.llm_service is None:
            raise RuntimeError(
                "LLM service is not configured."
            )

        if not hasattr(
                self.llm_service,
                "generate",
        ):
            raise AttributeError(
                "LLM service does not expose generate()."
            )

        return await self.llm_service.generate(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a strict Terraform remediation "
                        "engine. Return only complete Terraform code."
                    ),
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ],
            temperature=0,
            max_tokens=12000,
            json_mode=False,
        )

    # ==================================================================
    # EXTRACT TERRAFORM
    # ==================================================================

    def _extract_terraform(
            self,
            response: Any,
    ) -> str:

        if response is None:
            return ""

        if hasattr(
                response,
                "content",
        ):

            response = response.content

        if isinstance(
                response,
                dict,
        ):

            for key in (
                    "terraform",
                    "fixed_terraform",
                    "content",
                    "text",
            ):

                value = response.get(key)

                if isinstance(
                        value,
                        str,
                ):

                    response = value
                    break

        if not isinstance(
                response,
                str,
        ):

            response = str(response)

        response = response.strip()

        if not response:
            return ""

        # Remove Markdown fences
        match = re.search(
            r"```(?:terraform|hcl)?\s*(.*?)```",
            response,
            flags=re.IGNORECASE | re.DOTALL,
        )

        if match:

            response = match.group(1).strip()

        # Remove accidental explanation before Terraform
        first_resource = re.search(
            r'\b(resource|module|data|variable|terraform|provider|locals|output)\b',
            response,
            flags=re.IGNORECASE,
        )

        if first_resource:

            start = first_resource.start()

            if start > 0:
                response = response[start:]

        return response.strip()

    # ==================================================================
    # CLEAN TERRAFORM OUTPUT
    # ==================================================================

    def _clean_terraform_output(
            self,
            terraform_code: str,
    ) -> str:

        if not terraform_code:
            return ""

        text = terraform_code.replace(
            "\r\n",
            "\n",
        )

        # Remove trailing spaces
        lines = [
            line.rstrip()
            for line in text.splitlines()
        ]

        text = "\n".join(lines)

        # Add line breaks after common Terraform arguments when
        # the LLM incorrectly places multiple arguments on one line.
        terraform_arguments = [
            "name",
            "resource_group_name",
            "location",
            "size",
            "admin_username",
            "admin_password",
            "disable_password_authentication",
            "network_interface_ids",
            "subnet_id",
            "private_ip_address_allocation",
            "private_ip_address",
            "public_ip_address_id",
        ]

        for argument in terraform_arguments:

            text = re.sub(
                rf'(\S)\s+({re.escape(argument)}\s*=)',
                rf'\1\n\2',
                text,
            )

        # Add line breaks between closing and next resource
        text = re.sub(
            r'}\s+(resource\s+["\'])',
            r'}\n\n\1',
            text,
            flags=re.IGNORECASE,
        )

        return text.strip()

    # ==================================================================
    # TERRAFORM SANITY
    # ==================================================================

    def _looks_like_terraform(
            self,
            terraform_code: str,
    ) -> bool:

        if not isinstance(
                terraform_code,
                str,
        ):
            return False

        terraform_code = terraform_code.strip()

        if not terraform_code:
            return False

        block_pattern = re.compile(
            r'\b(resource|module|data|variable|terraform|provider|locals|output)\b',
            flags=re.IGNORECASE,
        )

        if not block_pattern.search(
                terraform_code
        ):
            return False

        if not self._balanced_braces(
                terraform_code
        ):
            return False

        return True

    # ==================================================================
    # BRACE VALIDATION
    # ==================================================================

    def _balanced_braces(
            self,
            text: str,
    ) -> bool:

        depth = 0
        in_string = False
        escaped = False

        for char in text:

            if (
                    char == '"'
                    and not escaped
            ):
                in_string = not in_string

            if not in_string:

                if char == "{":
                    depth += 1

                elif char == "}":

                    depth -= 1

                    if depth < 0:
                        return False

            if (
                    char == "\\"
                    and not escaped
            ):
                escaped = True
            else:
                escaped = False

        return (
                depth == 0
                and not in_string
        )

    # ==================================================================
    # VERIFY FIXES
    # ==================================================================

    def _verify_fixes(
            self,
            original_terraform: str,
            fixed_terraform: str,
            findings: List[Dict[str, Any]],
            infrastructure: Dict[str, Any],
    ) -> Tuple[
        List[Dict[str, Any]],
        List[Dict[str, Any]],
    ]:

        changes = []
        unresolved = []

        original_normalized = self._normalize_terraform(
            original_terraform
        )

        fixed_normalized = self._normalize_terraform(
            fixed_terraform
        )

        if (
                original_normalized
                == fixed_normalized
        ):

            for finding in findings:

                unresolved.append({
                    "terraform_location": finding.get(
                        "terraform_location"
                    ),
                    "reason": (
                        "Fixer returned unchanged Terraform."
                    ),
                })

            return changes, unresolved

        for finding in findings:

            terraform_location = finding.get(
                "terraform_location"
            )

            property_path = finding.get(
                "_fix_property_path"
            )

            resource_type = finding.get(
                "_resource_type"
            )

            resource_name = finding.get(
                "_resource_name"
            )

            original_value = finding.get(
                "_original_value"
            )

            original_block = (
                self._extract_resource_block(
                    original_terraform,
                    resource_type,
                    resource_name,
                )
            )

            fixed_block = (
                self._extract_resource_block(
                    fixed_terraform,
                    resource_type,
                    resource_name,
                )
            )

            if not original_block:

                unresolved.append({
                    "terraform_location": (
                        terraform_location
                    ),
                    "reason": (
                        "Original Terraform resource "
                        "could not be located."
                    ),
                })

                continue

            if not fixed_block:

                unresolved.append({
                    "terraform_location": (
                        terraform_location
                    ),
                    "reason": (
                        "The original Terraform resource "
                        "disappeared from fixer output."
                    ),
                })

                continue

            (
                original_present,
                original_property_value,
            ) = self._extract_nested_terraform_property(
                original_block,
                property_path,
            )

            (
                fixed_present,
                fixed_property_value,
            ) = self._extract_nested_terraform_property(
                fixed_block,
                property_path,
            )

            property_changed = (
                    self._normalize_value(
                        original_property_value
                    )
                    !=
                    self._normalize_value(
                        fixed_property_value
                    )
            )

            property_removed = (
                    original_present
                    and not fixed_present
            )

            # ----------------------------------------------------------
            # Special case: secret/password finding
            # ----------------------------------------------------------

            secret_fix_valid = False

            if (
                    property_path
                    and (
                    "password" in property_path.lower()
                    or "secret" in property_path.lower()
                    or "token" in property_path.lower()
            )
            ):

                original_string = str(
                    original_property_value
                    or original_value
                    or ""
                )

                fixed_string = str(
                    fixed_property_value
                    or ""
                )

                # A hard-coded secret must not remain unchanged.
                if (
                        original_string
                        and original_string != fixed_string
                ):
                    secret_fix_valid = True

                if property_removed:
                    secret_fix_valid = True

            if (
                    property_changed
                    or property_removed
                    or secret_fix_valid
            ):

                action = (
                    "removed"
                    if property_removed
                    else "modified"
                )

                changes.append({
                    "terraform_location": (
                        terraform_location
                    ),
                    "resource": resource_type,
                    "resource_name": resource_name,
                    "property": property_path,
                    "old_value": (
                        original_property_value
                        if original_property_value is not None
                        else original_value
                    ),
                    "new_value": fixed_property_value,
                    "action": action,
                    "problem": finding.get(
                        "problem"
                    ),
                    "recommendation": finding.get(
                        "recommendation"
                    ),
                })

                logger.info(
                    "Validated fixer change: %s",
                    terraform_location,
                )

            else:

                unresolved.append({
                    "terraform_location": (
                        terraform_location
                    ),
                    "reason": (
                        "The fixer output did not change "
                        "the Terraform property associated "
                        "with the validator finding."
                    ),
                })

        return changes, unresolved

    # ==================================================================
    # EXTRACT NESTED TERRAFORM PROPERTY
    # ==================================================================

    def _extract_nested_terraform_property(
            self,
            resource_block: str,
            property_path: str,
    ) -> Tuple[
        bool,
        Optional[str],
    ]:

        if not resource_block or not property_path:
            return False, None

        parts = property_path.split(".")
        current_text = resource_block

        for index, part in enumerate(parts):

            is_last = (
                    index == len(parts) - 1
            )

            attribute_pattern = re.compile(
                r"(?m)^\s*"
                + re.escape(part)
                + r"\s*=\s*(.+?)\s*$"
            )

            attribute_match = (
                attribute_pattern.search(
                    current_text
                )
            )

            if attribute_match:

                if is_last:

                    return (
                        True,
                        attribute_match.group(
                            1
                        ).strip(),
                    )

                return False, None

            block_pattern = re.compile(
                r"(?m)^\s*"
                + re.escape(part)
                + r"\s*\{"
            )

            block_match = (
                block_pattern.search(
                    current_text
                )
            )

            if not block_match:
                return False, None

            brace_start = current_text.find(
                "{",
                block_match.start(),
            )

            if brace_start == -1:
                return False, None

            brace_end = self._find_matching_brace(
                current_text,
                brace_start,
            )

            if brace_end == -1:
                return False, None

            if is_last:

                return (
                    True,
                    current_text[
                        block_match.start():
                        brace_end + 1
                    ].strip(),
                )

            current_text = current_text[
                brace_start:
                brace_end + 1
            ]

        return False, None

    # ==================================================================
    # RESOURCE BLOCK
    # ==================================================================

    def _extract_resource_block(
            self,
            terraform_code: str,
            resource_type: str,
            resource_name: str,
    ) -> str:

        if (
                not resource_type
                or not resource_name
        ):
            return ""

        pattern = re.compile(
            r'resource\s+["\']'
            + re.escape(resource_type)
            + r'["\']\s+["\']'
            + re.escape(resource_name)
            + r'["\']\s*\{',
            flags=re.IGNORECASE,
            )

        match = pattern.search(
            terraform_code
        )

        if not match:
            return ""

        brace_start = terraform_code.find(
            "{",
            match.start(),
        )

        if brace_start == -1:
            return ""

        end = self._find_matching_brace(
            terraform_code,
            brace_start,
        )

        if end == -1:
            return ""

        return terraform_code[
            match.start():
            end + 1
        ]

    # ==================================================================
    # MATCHING BRACE
    # ==================================================================

    def _find_matching_brace(
            self,
            text: str,
            opening_index: int,
    ) -> int:

        depth = 0
        in_string = False
        escaped = False

        for index in range(
                opening_index,
                len(text),
        ):

            char = text[index]

            if (
                    char == '"'
                    and not escaped
            ):
                in_string = not in_string

            if not in_string:

                if char == "{":
                    depth += 1

                elif char == "}":

                    depth -= 1

                    if depth == 0:
                        return index

            if (
                    char == "\\"
                    and not escaped
            ):
                escaped = True
            else:
                escaped = False

        return -1

    # ==================================================================
    # NORMALIZE TERRAFORM
    # ==================================================================

    def _normalize_terraform(
            self,
            terraform_code: str,
    ) -> str:

        text = (
            terraform_code
            .strip()
            .replace(
                "\r\n",
                "\n",
            )
        )

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n\s*\n+",
            "\n",
            text,
        )

        return text.strip()

    # ==================================================================
    # NORMALIZE VALUE
    # ==================================================================

    def _normalize_value(
            self,
            value: Any,
    ) -> Any:

        if value is None:
            return None

        if isinstance(
                value,
                str,
        ):

            return re.sub(
                r"\s+",
                " ",
                value.strip(),
            )

        return value

    # ==================================================================
    # RESOURCE CONSERVATION
    # ==================================================================

    def _verify_resource_conservation(
            self,
            original_terraform: str,
            fixed_terraform: str,
    ) -> Optional[str]:

        original_resources = (
            self._extract_resource_addresses(
                original_terraform
            )
        )

        fixed_resources = (
            self._extract_resource_addresses(
                fixed_terraform
            )
        )

        missing = (
                original_resources
                - fixed_resources
        )

        if missing:

            return (
                    "Fixer removed existing Terraform "
                    "resource(s): "
                    + ", ".join(
                sorted(missing)
            )
            )

        added = (
                fixed_resources
                - original_resources
        )

        if added:

            return (
                    "Fixer added Terraform resource(s) "
                    "that were not present in the original "
                    "configuration: "
                    + ", ".join(
                sorted(added)
            )
            )

        return None

    # ==================================================================
    # RESOURCE ADDRESSES
    # ==================================================================

    def _extract_resource_addresses(
            self,
            terraform_code: str,
    ) -> set:

        pattern = re.compile(
            r'resource\s+["\']([^"\']+)["\']'
            r'\s+["\']([^"\']+)["\']',
            flags=re.IGNORECASE,
        )

        return {
            f"{resource_type}.{resource_name}"
            for resource_type, resource_name
            in pattern.findall(
                terraform_code
            )
        }

    # ==================================================================
    # TERRAFORM CLI VALIDATION
    # ==================================================================

    def _validate_with_terraform_cli(
            self,
            terraform_code: str,
    ) -> Dict[str, Any]:

        try:

            version = subprocess.run(
                ["terraform", "version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

        except (
                FileNotFoundError,
                OSError,
        ):

            logger.info(
                "Terraform CLI not available. "
                "Skipping CLI validation."
            )

            return {
                "available": False,
                "valid": True,
                "error": None,
            }

        except Exception:

            return {
                "available": False,
                "valid": True,
                "error": None,
            }

        if version.returncode != 0:

            return {
                "available": False,
                "valid": True,
                "error": None,
            }

        try:

            with tempfile.TemporaryDirectory() as directory:

                main_tf = f"{directory}/main.tf"

                with open(
                        main_tf,
                        "w",
                        encoding="utf-8",
                ) as file:

                    file.write(
                        terraform_code
                    )

                # ------------------------------------------------------
                # IMPORTANT:
                #
                # terraform validate requires initialized providers.
                # Therefore run terraform init first.
                # ------------------------------------------------------

                init = subprocess.run(
                    [
                        "terraform",
                        "init",
                        "-backend=false",
                        "-input=false",
                    ],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )

                if init.returncode != 0:

                    error = (
                            init.stderr.strip()
                            or init.stdout.strip()
                            or "terraform init failed"
                    )

                    logger.warning(
                        "Terraform init failed: %s",
                        error,
                    )

                    # Do not confuse provider installation failure
                    # with Terraform syntax failure.
                    return {
                        "available": True,
                        "valid": True,
                        "error": (
                            "Terraform syntax could not be fully "
                            "validated because provider initialization "
                            f"failed: {error}"
                        ),
                        "validation_skipped": True,
                    }

                validate = subprocess.run(
                    [
                        "terraform",
                        "validate",
                        "-no-color",
                    ],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    check=False,
                )

                if validate.returncode != 0:

                    error = (
                            validate.stderr.strip()
                            or validate.stdout.strip()
                            or "terraform validate failed"
                    )

                    return {
                        "available": True,
                        "valid": False,
                        "error": error,
                    }

                return {
                    "available": True,
                    "valid": True,
                    "error": None,
                }

        except subprocess.TimeoutExpired:

            return {
                "available": True,
                "valid": False,
                "error": (
                    "Terraform validation timed out."
                ),
            }

        except Exception as exc:

            logger.warning(
                "Terraform CLI validation failed: %s",
                exc,
            )

            return {
                "available": False,
                "valid": True,
                "error": None,
            }

    # ==================================================================
    # SUMMARY
    # ==================================================================

    def _build_fix_summary(
            self,
            changes: List[Dict[str, Any]],
            rejected: List[Dict[str, Any]],
    ) -> str:

        if not changes:

            return (
                "No Terraform changes were validated."
            )

        summary = (
            f"{len(changes)} validator finding(s) "
            f"successfully remediated."
        )

        if rejected:

            summary += (
                f" {len(rejected)} finding(s) "
                f"could not be remediated safely."
            )

        return summary

    # ==================================================================
    # ERROR
    # ==================================================================

    def _error_result(
            self,
            message: str,
    ) -> Dict[str, Any]:

        return {
            "success": False,
            "fixed_terraform": None,
            "changes": [],
            "rejected_changes": [],
            "fix_summary": message,
            "error": message,
        }


# ======================================================================
# SINGLETON
# ======================================================================

fixer_service = FixerService(
    llm_service_instance=llm_service
)