import json
import logging
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from app.services.llm_service import llm_service


logger = logging.getLogger(__name__)


class ValidatorService:
    """
    Dynamic Terraform / Azure evidence-grounded validator.

    PRINCIPLES
    ----------
    1. Terraform is the source of truth.
    2. Azure retrieved documents are the only compliance evidence.
    3. Terraform resources/properties/configurations are discovered dynamically.
    4. Property controls and configuration controls are evaluated separately.
    5. LLM interprets Azure evidence.
    6. Python owns Terraform identity and final structural validation.
    7. Evidence must physically exist in retrieved documents.
    8. Missing evidence => UNKNOWN, never compliant.
    9. Unsupported evidence => UNSUPPORTED, never compliant.
    10. Cross-service inference is rejected.
    11. Cross-control inference is rejected.
    12. Secrets are redacted before LLM analysis.
    13. Property operators describe documented COMPLIANCE conditions.
    14. Python independently verifies property violations.
    15. Configuration findings use multiple evidence passages when needed.
    16. Configuration analysis evaluates the COMPLETE nested block.
    17. Coverage counts only controls that were actually evaluated.
    18. A finding is accepted only after structural/evidence validation.
    """

    # ==============================================================
    # CONSTANTS
    # ==============================================================

    VALID_OPERATORS = {
        "eq",
        "neq",
        "gt",
        "gte",
        "lt",
        "lte",
        "in",
        "nin",
        "contains",
        "not_contains",
    }

    VALID_SEVERITIES = {
        "critical",
        "high",
        "medium",
        "low",
    }

    SECRET_PROPERTIES = {
        "password",
        "admin_password",
        "administrator_password",
        "administrator_login_password",
        "secret",
        "client_secret",
        "token",
        "private_key",
        "privatekey",
        "api_key",
        "apikey",
        "access_key",
        "accesskey",
        "credential",
        "credentials",
    }

    NON_VALIDATABLE_PROPERTY_NAMES = {
        "name",
        "location",
        "resource_group_name",
        "resource_group",
        "description",
        "terraform_path_id",
        "admin_username",
    }

    STRUCTURAL_BLOCK_NAMES = {
        "ip_configuration",
        "network_profile",
        "identity",
        "os_disk",
        "storage_os_disk",
        "boot_diagnostics",
        "timeouts",
        "tags",
    }

    MAX_DOCUMENTS_PER_PROPERTY = 12
    MAX_DOCUMENTS_PER_CONFIGURATION = 12
    MAX_CONFIGURATION_EVIDENCE_ITEMS = 8

    EVIDENCE_DOCUMENT_CHARS = 14000
    FINDING_DOCUMENT_CHARS = 14000
    CONFIGURATION_DOCUMENT_CHARS = 12000

    EVIDENCE_MAX_TOKENS = 550
    FINDING_MAX_TOKENS = 1300
    CONFIGURATION_FINDING_MAX_TOKENS = 1800

    MIN_CONCLUSIVE_CONTROLS = 3
    MIN_CONCLUSIVE_COVERAGE = 0.30

    SEVERITY_PENALTIES = {
        "Critical": 25,
        "High": 12,
        "Medium": 6,
        "Low": 2,
    }

    # Default values for Terraform properties when not explicitly set
    DEFAULT_VALUES = {
        "azurerm_mssql_server": {
            "public_network_access_enabled": True,
        },
        "azurerm_storage_account": {
            "https_traffic_only_enabled": False,
            "public_network_access_enabled": True,
            "min_tls_version": "TLS1_2",
        },
        "azurerm_app_service": {
            "https_only": False,
        },
        "azurerm_key_vault": {
            "purge_protection_enabled": False,
            "soft_delete_retention_days": 90,
        },
        "azurerm_kubernetes_cluster": {
            "role_based_access_control_enabled": True,
        },
        "azurerm_linux_virtual_machine": {
            "disable_password_authentication": True,
        },
    }

    # Resource aliases for semantic matching (Azure documentation vocabulary)
    RESOURCE_ALIASES = {
        "azurerm_storage_account": [
            "storage account",
            "storage accounts",
            "azure storage",
            "blob storage",
            "storage service",
        ],
        "azurerm_kubernetes_cluster": [
            "kubernetes",
            "aks",
            "kubernetes cluster",
            "aks cluster",
            "azure kubernetes",
            "kubernetes service",
            "control plane",
            "azure kubernetes service",
            "aks service",
            "kubernetes",
            "k8s",
        ],
        "azurerm_linux_virtual_machine": [
            "linux virtual machine",
            "linux vm",
            "virtual machine",
            "azure linux",
            "linux vm",
            "vm",
        ],
        "azurerm_key_vault": [
            "key vault",
            "keyvault",
            "vault",
            "azure key vault",
            "secrets vault",
        ],
        "azurerm_network_security_group": [
            "network security group",
            "nsg",
            "security group",
            "azure nsg",
            "network security",
        ],
        "azurerm_virtual_network": [
            "virtual network",
            "vnet",
            "azure virtual network",
            "virtual network address",
        ],
        "azurerm_mssql_server": [
            "sql server",
            "mssql",
            "azure sql",
            "sql database",
            "logical server",
        ],
        "azurerm_app_service": [
            "app service",
            "azure app service",
            "web app",
            "application service",
        ],
    }

    # Property aliases for semantic matching (Azure documentation vocabulary)
    PROPERTY_ALIASES = {
        "min_tls_version": [
            "minimum tls version",
            "minimum tls",
            "tls 1.2",
            "tls1.2",
            "tls 1.2 minimum",
            "minimum version",
            "secure transfer",
            "encrypted connection",
            "tls version",
            "transport layer security",
        ],
        "https_traffic_only_enabled": [
            "https only",
            "https-only",
            "secure transfer required",
            "secure transfer",
            "https traffic",
            "http traffic",
            "unencrypted http",
            "tls",
            "encrypted transfer",
            "secure transmission",
        ],
        "public_network_access_enabled": [
            "public network access",
            "public access",
            "public traffic",
            "public endpoint",
            "network access",
            "disable public",
            "block public",
            "public connectivity",
            "internet access",
        ],
        "role_based_access_control_enabled": [
            "role based access control",
            "role-based access control",
            "rbac",
            "kubernetes rbac",
            "cluster authorization",
            "authorization",
            "access control",
            "azure rbac",
            "aks rbac",
            "control plane access",
            "cluster access",
        ],
        "network_policy": [
            "network policy",
            "network policies",
            "pod network policy",
            "pod isolation",
            "network isolation",
            "traffic policy",
            "network security policy",
            "calico",
            "azure policy",
            "container network policy",
            "network security group",
            "nsg",
        ],
        "network_plugin": [
            "network plugin",
            "networking plugin",
            "container networking",
            "kubernetes networking",
            "azure networking",
            "networking model",
            "azure cni",
            "kubenet",
            "network interface",
            "container network interface",
            "cni",
        ],
        "disable_password_authentication": [
            "disable password authentication",
            "password authentication",
            "password-based authentication",
            "password based authentication",
            "ssh password",
            "ssh key",
            "ssh keys",
            "linux virtual machine",
            "linux vm",
            "disable password",
            "password login",
            "ssh authentication",
        ],
        "purge_protection_enabled": [
            "purge protection",
            "purge-protection",
            "permanent deletion",
            "deletion protection",
            "irreversible deletion",
            "purge",
            "soft delete",
        ],
        "soft_delete_retention_days": [
            "soft delete",
            "soft-delete",
            "retention period",
            "retention days",
            "deleted secrets",
            "recover deleted secrets",
            "retention",
            "recover deleted",
        ],
        "https_only": [
            "https only",
            "https",
            "secure http",
            "tls 1.2",
            "https traffic",
        ],
        "container_access_type": [
            "container access",
            "anonymous access",
            "anonymous blob",
            "public blob",
            "blob access",
            "public access",
        ],
        "address_space": [
            "address space",
            "vnet address",
            "address prefix",
            "cidr",
            "network address",
        ],
    }

    # ==============================================================
    # INIT
    # ==============================================================

    def __init__(
            self,
            llm_service_instance=None,
            retriever_service=None,
    ):
        self.llm_service = (
            llm_service_instance
            if llm_service_instance is not None
            else llm_service
        )

        self.retriever_service = retriever_service

        # Cache for child properties per parent path
        self._child_properties_cache: Dict[str, List[Dict[str, Any]]] = {}

        logger.info(
            "ValidatorService initialized | llm=%s | retriever=%s",
            self.llm_service is not None,
            self.retriever_service is not None,
            )

    # ==============================================================
    # PUBLIC API
    # ==============================================================

    async def validate(
            self,
            infrastructure: Dict[str, Any],
            retrieved_documents: Optional[List[Dict[str, Any]]] = None,
            reranked_documents: Optional[List[Dict[str, Any]]] = None,
            parse_status: Optional[str] = None,
            parse_error: Optional[str] = None,
    ) -> Dict[str, Any]:

        logger.info(
            "========== DYNAMIC TERRAFORM/AZURE VALIDATOR =========="
        )

        # ----------------------------------------------------------
        # 1. PARSER VALIDATION
        # ----------------------------------------------------------

        if parse_status == "failed" or parse_error:
            return self._build_result(
                findings=[],
                validation_performed=False,
                analysis_conclusive=False,
                context_found=False,
                score_override=0,
                error=parse_error or "Terraform parsing failed.",
                summary=(
                    "Terraform validation could not be performed "
                    "because parsing failed."
                ),
            )

        if not isinstance(infrastructure, dict):
            return self._build_result(
                findings=[],
                validation_performed=False,
                analysis_conclusive=False,
                context_found=False,
                score_override=0,
                error="Invalid infrastructure structure.",
                summary=(
                    "The parsed Terraform infrastructure has "
                    "an invalid structure."
                ),
            )

        resources = infrastructure.get("resources", [])

        if not isinstance(resources, list) or not resources:
            return self._build_result(
                findings=[],
                validation_performed=False,
                analysis_conclusive=False,
                context_found=False,
                score_override=0,
                error="No Terraform resources were found.",
                summary="No Terraform resources were found.",
            )

        # ----------------------------------------------------------
        # 2. TERRAFORM CATALOG
        # ----------------------------------------------------------

        terraform_catalog = self._build_terraform_catalog(
            infrastructure
        )

        if not terraform_catalog:
            return self._build_result(
                findings=[],
                validation_performed=False,
                analysis_conclusive=False,
                context_found=False,
                score_override=0,
                error="No Terraform properties were found.",
                summary="No Terraform properties were found.",
            )

        # ----------------------------------------------------------
        # 3. DOCUMENT SELECTION
        # ----------------------------------------------------------

        documents = self._select_documents(
            retrieved_documents=retrieved_documents,
            reranked_documents=reranked_documents,
        )

        context_found = bool(documents)

        if not documents and self.retriever_service is None:
            return self._build_result(
                findings=[],
                validation_performed=False,
                analysis_conclusive=False,
                context_found=False,
                score_override=0,
                error="No Azure documents and no retriever service.",
                summary=(
                    "No Azure documentation is available "
                    "for validation."
                ),
            )

        if self.llm_service is None:
            return self._build_result(
                findings=[],
                validation_performed=False,
                analysis_conclusive=False,
                context_found=context_found,
                score_override=0,
                error="LLM service is not configured.",
                summary="No LLM service is configured.",
            )

        # ----------------------------------------------------------
        # 4. PROPERTY CANDIDATES
        # ----------------------------------------------------------

        property_candidates = [
            candidate
            for candidate in self._build_all_property_candidates(
                terraform_catalog,
                documents=documents,
            )
            if self._is_concrete_property_candidate(candidate)
               and not self._is_non_validatable_property(candidate)
        ]

        # ----------------------------------------------------------
        # 5. CONFIGURATION CANDIDATES
        # ----------------------------------------------------------

        configuration_candidates = (
            self._build_configuration_candidates(
                infrastructure=infrastructure,
                documents=documents,
            )
        )

        logger.warning(
            "========== VALIDATION CANDIDATES =========="
        )

        logger.warning(
            "PROPERTY CANDIDATES=%d",
            len(property_candidates),
        )

        logger.warning(
            "CONFIGURATION CANDIDATES=%d",
            len(configuration_candidates),
        )

        for candidate in configuration_candidates:
            logger.warning(
                "CONFIG TARGET=%s",
                candidate["configuration_path"],
            )

        if not property_candidates and not configuration_candidates:
            return self._build_result(
                findings=[],
                validation_performed=False,
                analysis_conclusive=False,
                context_found=context_found,
                score_override=0,
                error="No validation candidates were found.",
                summary=(
                    "No Terraform property or configuration "
                    "candidates were found."
                ),
            )

        # ----------------------------------------------------------
        # 6. TRACKING
        # ----------------------------------------------------------

        validated_findings: List[Dict[str, Any]] = []

        evaluated_controls: Set[str] = set()
        supported_controls: Set[str] = set()
        unsupported_controls: Set[str] = set()
        unknown_controls: Set[str] = set()

        # ==========================================================
        # PROPERTY VALIDATION
        # ==========================================================

        logger.warning(
            "========== PROPERTY VALIDATION (%d) ==========",
            len(property_candidates),
        )

        for candidate in property_candidates:

            path = self._clean_string(
                candidate["terraform_path"]
            )

            logger.info(
                "PROPERTY TARGET=%s",
                path,
            )

            property_documents = (
                await self._retrieve_property_evidence(
                    candidate,
                    documents,
                )
            )

            if not property_documents:
                logger.debug(
                    "No property documents | %s",
                    path,
                )
                unknown_controls.add(f"property::{path}")
                continue

            property_documents = self._rank_documents(
                property_documents
            )[: self.MAX_DOCUMENTS_PER_PROPERTY]

            logger.debug(
                "PROPERTY DOCUMENTS | path=%s | count=%d",
                path,
                len(property_documents),
            )

            evidence = await self._extract_property_evidence(
                candidate,
                property_documents,
            )

            if not evidence:
                logger.debug(
                    "No direct property evidence | %s",
                    path,
                )
                unknown_controls.add(f"property::{path}")
                continue

            logger.debug(
                "PROPERTY EVIDENCE FOUND | %s | source=%s | page=%s",
                path,
                evidence["document"].get("source"),
                evidence["document"].get("page"),
            )

            # Relevance filter: keep it, but make it more permissive
            if not self._property_evidence_is_relevant(
                    candidate=candidate,
                    evidence_quote=evidence["quote"],
            ):
                logger.warning(
                    "PROPERTY EVIDENCE REJECTED AS IRRELEVANT | "
                    "path=%s | quote=%s",
                    path,
                    evidence["quote"],
                )
                unknown_controls.add(f"property::{path}")
                continue

            finding = await self._analyze_property(
                candidate=candidate,
                documents=property_documents,
                evidence_quote=evidence["quote"],
                document=evidence["document"],
            )

            analysis_status = (
                finding.pop("_analysis_status", None)
                if finding
                else None
            )

            if analysis_status == "unsupported":
                unsupported_controls.add(
                    f"property::{path}"
                )
                logger.info(
                    "PROPERTY UNSUPPORTED | %s",
                    path,
                )
                continue

            if analysis_status == "compliant":
                supported_controls.add(
                    f"property::{path}"
                )
                evaluated_controls.add(
                    f"property::{path}"
                )
                logger.info(
                    "PROPERTY COMPLIANT | %s",
                    path,
                )
                continue

            if not finding:
                logger.debug(
                    "PROPERTY ANALYSIS UNKNOWN | %s",
                    path,
                )
                unknown_controls.add(f"property::{path}")
                continue

            supported_controls.add(
                f"property::{path}"
            )
            evaluated_controls.add(
                f"property::{path}"
            )

            finding.update(
                {
                    "resource": candidate["resource_type"],
                    "resource_name": candidate["resource_name"],
                    "terraform_path": candidate["terraform_path"],
                    "observed_value": candidate["observed_value"],
                    "evidence_quote": evidence["quote"],
                    "control_type": "property",
                }
            )

            if not self._accept_finding(
                    finding=finding,
                    candidate=candidate,
                    documents=property_documents,
                    terraform_catalog=terraform_catalog,
                    is_configuration=False,
            ):
                logger.warning(
                    "PROPERTY FINDING REJECTED | %s",
                    path,
                )
                unknown_controls.add(f"property::{path}")
                continue

            validated_findings.append(finding)

            logger.warning(
                "PROPERTY FINDING ACCEPTED | %s | severity=%s",
                path,
                finding.get("severity"),
            )

        # ==========================================================
        # CONFIGURATION VALIDATION
        # ==========================================================

        logger.warning(
            "========== CONFIGURATION VALIDATION (%d) ==========",
            len(configuration_candidates),
        )

        for candidate in configuration_candidates:

            path = self._clean_string(
                candidate["configuration_path"]
            )

            logger.warning(
                "CONFIGURATION TARGET=%s",
                path,
            )

            # Retrieve parent and child documents
            configuration_documents = (
                await self._retrieve_configuration_evidence(
                    candidate,
                    documents,
                )
            )

            logger.warning(
                "CONFIGURATION DOCUMENTS | path=%s | count=%d",
                path,
                len(configuration_documents),
            )

            if not configuration_documents:
                logger.info(
                    "No configuration documents | %s",
                    path,
                )
                unknown_controls.add(f"configuration::{path}")
                continue

            evidence = await self._extract_configuration_evidence(
                candidate=candidate,
                documents=configuration_documents,
                terraform_catalog=terraform_catalog,
            )

            evidence_count = (
                len(evidence.get("items", []))
                if evidence
                else 0
            )

            logger.warning(
                "CONFIGURATION EVIDENCE | path=%s | evidence_count=%d",
                path,
                evidence_count,
            )

            if not evidence:
                logger.info(
                    "No direct configuration evidence | %s",
                    path,
                )
                unknown_controls.add(f"configuration::{path}")
                continue

            finding = await self._analyze_configuration(
                candidate=candidate,
                documents=configuration_documents,
                evidence=evidence,
            )

            analysis_status = (
                finding.pop("_analysis_status", None)
                if finding
                else None
            )

            logger.warning(
                "CONFIGURATION ANALYSIS | path=%s | status=%s",
                path,
                analysis_status or "unknown",
                )

            if analysis_status == "unsupported":
                unsupported_controls.add(
                    f"configuration::{path}"
                )
                logger.info(
                    "CONFIGURATION UNSUPPORTED | %s",
                    path,
                )
                continue

            if analysis_status == "compliant":
                supported_controls.add(
                    f"configuration::{path}"
                )
                evaluated_controls.add(
                    f"configuration::{path}"
                )
                logger.info(
                    "CONFIGURATION COMPLIANT | %s",
                    path,
                )
                continue

            if not finding:
                logger.debug(
                    "CONFIGURATION ANALYSIS UNKNOWN | %s",
                    path,
                )
                unknown_controls.add(f"configuration::{path}")
                continue

            supported_controls.add(
                f"configuration::{path}"
            )
            evaluated_controls.add(
                f"configuration::{path}"
            )

            finding.update(
                {
                    "resource": candidate["resource_type"],
                    "resource_name": candidate["resource_name"],
                    "terraform_path": candidate["configuration_path"],
                    "observed_value": candidate["observed_value"],
                    "evidence_quote": finding.get(
                        "evidence_quote",
                        "",
                    ),
                    "control_type": "configuration",
                }
            )

            if not self._accept_finding(
                    finding=finding,
                    candidate=candidate,
                    documents=configuration_documents,
                    terraform_catalog=terraform_catalog,
                    is_configuration=True,
            ):
                logger.warning(
                    "CONFIGURATION FINDING REJECTED | %s",
                    path,
                )
                unknown_controls.add(f"configuration::{path}")
                continue

            validated_findings.append(finding)

            logger.warning(
                "CONFIGURATION FINDING ACCEPTED | %s | severity=%s",
                path,
                finding.get("severity"),
            )

        # ==========================================================
        # DEDUPLICATION
        # ==========================================================

        validated_findings = self._deduplicate_findings(
            validated_findings
        )

        # ==========================================================
        # COVERAGE
        # ==========================================================

        total_controls = (
                len(property_candidates)
                + len(configuration_candidates)
        )

        evaluated_count = len(evaluated_controls)
        unsupported_count = len(unsupported_controls)
        unknown_count = len(unknown_controls)

        property_coverage = self._coverage(
            evaluated_controls,
            "property::",
            len(property_candidates),
        )

        configuration_coverage = self._coverage(
            evaluated_controls,
            "configuration::",
            len(configuration_candidates),
        )

        coverage = (
            evaluated_count / total_controls
            if total_controls
            else 0.0
        )

        logger.warning(
            "VALIDATION COVERAGE | "
            "total=%d | evaluated=%d | supported=%d | "
            "unsupported=%d | unknown=%d | overall=%.2f | "
            "property=%.2f | configuration=%.2f",
            total_controls,
            evaluated_count,
            len(supported_controls),
            unsupported_count,
            unknown_count,
            coverage,
            property_coverage,
            configuration_coverage,
        )

        # ==========================================================
        # SCORE (basé uniquement sur les findings validés)
        # ==========================================================

        score = self._calculate_infrastructure_score(
            validated_findings
        )

        # ==========================================================
        # NON-COMPLIANT
        # ==========================================================

        if validated_findings:
            return self._build_result(
                findings=validated_findings,
                validation_performed=True,
                analysis_conclusive=True,
                context_found=context_found,
                score_override=score,
                coverage=coverage,
                property_coverage=property_coverage,
                configuration_coverage=configuration_coverage,
                evaluated_count=evaluated_count,
                total_controls=total_controls,
                unsupported_count=unsupported_count,
                unknown_count=unknown_count,
                retrieved_property_count=sum(
                    1
                    for x in evaluated_controls
                    if x.startswith("property::")
                ),
                conclusive_property_count=sum(
                    1
                    for x in evaluated_controls
                    if x.startswith("property::")
                ),
                configuration_count=len(
                    configuration_candidates
                ),
                conclusive_configuration_count=sum(
                    1
                    for x in evaluated_controls
                    if x.startswith("configuration::")
                ),
            )

        # ==========================================================
        # INCONCLUSIVE
        # ==========================================================

        analysis_conclusive = (
                evaluated_count >= self.MIN_CONCLUSIVE_CONTROLS
                and coverage >= self.MIN_CONCLUSIVE_COVERAGE
        )

        if not analysis_conclusive:
            summary = (
                "Terraform validation was performed, but Azure "
                "evidence coverage was insufficient to establish "
                "compliance conclusively. "
                f"Evaluated controls: "
                f"{evaluated_count}/{total_controls}. "
                f"Unsupported: {unsupported_count}. "
                f"Unknown: {unknown_count}. "
                f"Coverage: {coverage:.0%}."
            )

            return self._build_result(
                findings=[],
                validation_performed=True,
                analysis_conclusive=False,
                context_found=context_found,
                score_override=score,
                error="Insufficient Azure evidence coverage.",
                summary=summary,
                coverage=coverage,
                property_coverage=property_coverage,
                configuration_coverage=configuration_coverage,
                evaluated_count=evaluated_count,
                total_controls=total_controls,
                unsupported_count=unsupported_count,
                unknown_count=unknown_count,
                retrieved_property_count=sum(
                    1
                    for x in evaluated_controls
                    if x.startswith("property::")
                ),
                conclusive_property_count=sum(
                    1
                    for x in evaluated_controls
                    if x.startswith("property::")
                ),
                configuration_count=len(
                    configuration_candidates
                ),
                conclusive_configuration_count=sum(
                    1
                    for x in evaluated_controls
                    if x.startswith("configuration::")
                ),
            )

        # ==========================================================
        # COMPLIANT
        # ==========================================================

        summary = (
            "Infrastructure validation completed without "
            "evidence-grounded violations. "
            f"Evaluated controls: "
            f"{evaluated_count}/{total_controls}. "
            f"Coverage: {coverage:.0%}."
        )

        return self._build_result(
            findings=[],
            validation_performed=True,
            analysis_conclusive=True,
            context_found=context_found,
            score_override=100,
            error=None,
            summary=summary,
            coverage=coverage,
            property_coverage=property_coverage,
            configuration_coverage=configuration_coverage,
            evaluated_count=evaluated_count,
            total_controls=total_controls,
            unsupported_count=unsupported_count,
            unknown_count=unknown_count,
            retrieved_property_count=sum(
                1
                for x in evaluated_controls
                if x.startswith("property::")
            ),
            conclusive_property_count=sum(
                1
                for x in evaluated_controls
                if x.startswith("property::")
            ),
            configuration_count=len(
                configuration_candidates
            ),
            conclusive_configuration_count=sum(
                1
                for x in evaluated_controls
                if x.startswith("configuration::")
            ),
        )

    # ==============================================================
    # TERRAFORM CATALOG
    # ==============================================================

    def _build_terraform_catalog(
            self,
            infrastructure: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        catalog: List[Dict[str, Any]] = []

        for resource in infrastructure.get(
                "resources",
                [],
        ):

            if not isinstance(resource, dict):
                continue

            resource_type = self._clean_string(
                resource.get("type")
            )

            resource_name = self._clean_string(
                resource.get("name")
            )

            configuration = resource.get(
                "configuration",
                {},
            )

            if not resource_type or not resource_name:
                continue

            if not isinstance(configuration, dict):
                continue

            self._collect_catalog_items(
                value=configuration,
                current_path=(
                    f"{resource_type}.{resource_name}"
                ),
                resource_type=resource_type,
                resource_name=resource_name,
                output=catalog,
            )

        logger.info(
            "Terraform catalog built | entries=%d",
            len(catalog),
        )

        return catalog

    def _collect_catalog_items(
            self,
            value: Any,
            current_path: str,
            resource_type: str,
            resource_name: str,
            output: List[Dict[str, Any]],
    ) -> None:

        if isinstance(value, dict):

            for key, child in value.items():

                key = str(key).strip()

                if not key or key.startswith("__"):
                    continue

                child_path = (
                    f"{current_path}.{key}"
                )

                if isinstance(child, dict):

                    self._collect_catalog_items(
                        value=child,
                        current_path=child_path,
                        resource_type=resource_type,
                        resource_name=resource_name,
                        output=output,
                    )

                elif isinstance(child, list):

                    for index, item in enumerate(child):

                        item_path = (
                            f"{child_path}[{index}]"
                        )

                        if isinstance(
                                item,
                                (dict, list),
                        ):
                            self._collect_catalog_items(
                                value=item,
                                current_path=item_path,
                                resource_type=resource_type,
                                resource_name=resource_name,
                                output=output,
                            )
                        else:
                            output.append(
                                {
                                    "resource_type": resource_type,
                                    "resource_name": resource_name,
                                    "terraform_path": item_path,
                                    "property": (
                                        f"{key}[{index}]"
                                    ),
                                    "value": (
                                        self._safe_observed_value(
                                            item,
                                            item_path,
                                        )
                                    ),
                                }
                            )

                else:

                    output.append(
                        {
                            "resource_type": resource_type,
                            "resource_name": resource_name,
                            "terraform_path": child_path,
                            "property": key,
                            "value": (
                                self._safe_observed_value(
                                    child,
                                    child_path,
                                )
                            ),
                        }
                    )

            return

        if isinstance(value, list):

            for index, item in enumerate(value):

                item_path = (
                    f"{current_path}[{index}]"
                )

                if isinstance(
                        item,
                        (dict, list),
                ):
                    self._collect_catalog_items(
                        value=item,
                        current_path=item_path,
                        resource_type=resource_type,
                        resource_name=resource_name,
                        output=output,
                    )

    def _get_child_properties_from_catalog(
            self,
            parent_path: str,
            terraform_catalog: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Get all child properties of a parent path from the Terraform catalog.
        This is used to build child property candidates for configuration evidence.
        """
        cache_key = f"{parent_path}_{len(terraform_catalog)}"
        if cache_key in self._child_properties_cache:
            return self._child_properties_cache[cache_key]

        resource_type, resource_name = self._extract_resource_identity(parent_path)
        if not resource_type or not resource_name:
            return []

        prefix = f"{resource_type}.{resource_name}"
        relative_parent = self._relative_resource_path(parent_path, resource_type, resource_name)

        children: List[Dict[str, Any]] = []

        for item in terraform_catalog:
            item_path = self._clean_string(item.get("terraform_path"))
            if not item_path:
                continue

            if not item_path.startswith(parent_path + "."):
                continue

            # Skip if it's not directly below the parent (no intermediate blocks)
            remaining = item_path[len(parent_path) + 1:]
            if "." in remaining:
                continue

            children.append({
                "resource_type": item.get("resource_type"),
                "resource_name": item.get("resource_name"),
                "terraform_path": item_path,
                "property": item.get("property"),
                "value": item.get("value"),
            })

        self._child_properties_cache[cache_key] = children
        return children

    def _build_all_property_candidates(
            self,
            terraform_catalog: List[Dict[str, Any]],
            documents: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:

        candidates: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str, str]] = set()

        # ----------------------------------------------------------
        # 1. EXPLICIT TERRAFORM PROPERTIES
        # ----------------------------------------------------------

        for item in terraform_catalog:

            resource_type = self._clean_string(
                item.get("resource_type")
            )

            resource_name = self._clean_string(
                item.get("resource_name")
            )

            path = self._clean_string(
                item.get("terraform_path")
            )

            property_name = self._clean_string(
                item.get("property")
            )

            if (
                    not resource_type
                    or not resource_name
                    or not path
                    or not property_name
            ):
                continue

            key = (
                resource_type,
                resource_name,
                path,
            )

            if key in seen:
                continue

            seen.add(key)

            candidates.append(
                {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "terraform_path": path,
                    "property": property_name,
                    "observed_value": item.get("value"),
                    "value_source": "terraform_explicit",
                }
            )

        # ----------------------------------------------------------
        # 2. DEFAULT VALUES FOR MISSING PROPERTIES
        # ----------------------------------------------------------

        for document in documents or []:

            if not isinstance(document, dict):
                continue

            query_type = self._clean_string(
                document.get(
                    "query_type",
                    document.get("_retrieval_query_type", ""),
                )
            )

            if query_type != "terraform_property":
                continue

            path = self._clean_string(
                document.get(
                    "terraform_path",
                    document.get(
                        "_terraform_path",
                        document.get("terraform_path_id", ""),
                    ),
                )
            )

            if not path:
                continue

            resource_type, resource_name = (
                self._extract_resource_identity(path)
            )

            if not resource_type or not resource_name:
                continue

            relative = self._relative_resource_path(
                path,
                resource_type,
                resource_name,
            )

            if not relative:
                continue

            property_name = relative.split(".")[-1]
            property_name = re.sub(
                r"\[\d+\]$",
                "",
                property_name,
            )

            key = (
                resource_type,
                resource_name,
                path,
            )

            if key in seen:
                continue

            if resource_type not in self.DEFAULT_VALUES:
                continue

            if property_name not in self.DEFAULT_VALUES[resource_type]:
                continue

            default_value = self.DEFAULT_VALUES[resource_type][property_name]

            seen.add(key)

            candidates.append(
                {
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "terraform_path": path,
                    "property": property_name,
                    "observed_value": default_value,
                    "value_source": "terraform_provider_default",
                }
            )

            logger.info(
                "DEFAULT PROPERTY CANDIDATE | "
                "path=%s | value=%r",
                path,
                default_value,
            )

        return candidates

    # ==============================================================
    # CONFIGURATION DISCOVERY
    # ==============================================================

    def _build_configuration_candidates(
            self,
            infrastructure: Dict[str, Any],
            documents: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:

        candidates: Dict[
            str,
            Dict[str, Any],
        ] = {}

        # ----------------------------------------------------------
        # EXACT CONFIGURATION PATHS FROM RAG
        # ----------------------------------------------------------

        for doc in documents or []:

            if not isinstance(doc, dict):
                continue

            query_type = self._clean_string(
                doc.get(
                    "query_type",
                    doc.get(
                        "_retrieval_query_type",
                        "",
                    ),
                )
            )

            if query_type != "terraform_configuration":
                continue

            path = self._clean_string(
                doc.get(
                    "terraform_path",
                    doc.get(
                        "_terraform_path",
                        doc.get(
                            "configuration_path",
                            "",
                        ),
                    ),
                )
            )

            if not path:
                continue

            resource_type, resource_name = (
                self._extract_resource_identity(path)
            )

            if not resource_type or not resource_name:
                continue

            resource = self._find_resource(
                infrastructure,
                resource_type,
                resource_name,
            )

            if not resource:
                continue

            relative_path = (
                self._relative_resource_path(
                    path,
                    resource_type,
                    resource_name,
                )
            )

            full_configuration = resource.get(
                "configuration",
                {},
            )

            observed = self._resolve_terraform_path(
                full_configuration,
                relative_path,
            )

            if observed is None:
                logger.debug(
                    "Configuration path not found in Terraform | %s",
                    path,
                )
                continue

            if not isinstance(
                    observed,
                    (dict, list),
            ):
                logger.debug(
                    "Configuration path is scalar | %s",
                    path,
                )
                continue

            candidates[path] = {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "configuration_path": path,
                "observed_value": (
                    self._safe_configuration_snapshot(
                        observed,
                        path,
                    )
                ),
                "_full_configuration": full_configuration,
            }

        # ----------------------------------------------------------
        # FALLBACK DISCOVERY
        # ----------------------------------------------------------

        if not candidates:

            for resource in infrastructure.get(
                    "resources",
                    [],
            ):

                if not isinstance(resource, dict):
                    continue

                resource_type = self._clean_string(
                    resource.get("type")
                )

                resource_name = self._clean_string(
                    resource.get("name")
                )

                configuration = resource.get(
                    "configuration",
                    {},
                )

                full_configuration = resource.get(
                    "configuration",
                    {},
                )

                if (
                        not resource_type
                        or not resource_name
                        or not isinstance(
                    configuration,
                    dict,
                )
                ):
                    continue

                self._discover_blocks(
                    value=configuration,
                    current_path=(
                        f"{resource_type}.{resource_name}"
                    ),
                    resource_type=resource_type,
                    resource_name=resource_name,
                    output=candidates,
                    full_configuration=full_configuration,
                )

        return list(candidates.values())

    def _discover_blocks(
            self,
            value: Any,
            current_path: str,
            resource_type: str,
            resource_name: str,
            output: Dict[str, Dict[str, Any]],
            full_configuration: Optional[Dict[str, Any]] = None,
    ) -> None:

        if isinstance(value, dict):

            for key, child in value.items():

                key = str(key).strip()

                if not key or key.startswith("__"):
                    continue

                child_path = (
                    f"{current_path}.{key}"
                )

                if isinstance(child, dict):

                    leaf_count = self._count_leaves(
                        child
                    )

                    if (
                            leaf_count >= 2
                            and self._looks_like_configuration_block(
                        key,
                        child,
                    )
                    ):
                        output.setdefault(
                            child_path,
                            {
                                "resource_type": resource_type,
                                "resource_name": resource_name,
                                "configuration_path": child_path,
                                "observed_value": (
                                    self._safe_configuration_snapshot(
                                        child,
                                        child_path,
                                    )
                                ),
                                "_full_configuration": (
                                        full_configuration or {}
                                ),
                            },
                        )

                    self._discover_blocks(
                        value=child,
                        current_path=child_path,
                        resource_type=resource_type,
                        resource_name=resource_name,
                        output=output,
                        full_configuration=full_configuration,
                    )

                elif isinstance(child, list):

                    for index, item in enumerate(child):

                        item_path = (
                            f"{child_path}[{index}]"
                        )

                        if not isinstance(item, dict):
                            continue

                        leaf_count = self._count_leaves(
                            item
                        )

                        if (
                                leaf_count >= 2
                                and self._looks_like_configuration_block(
                            key,
                            item,
                        )
                        ):
                            output.setdefault(
                                item_path,
                                {
                                    "resource_type": resource_type,
                                    "resource_name": resource_name,
                                    "configuration_path": item_path,
                                    "observed_value": (
                                        self._safe_configuration_snapshot(
                                            item,
                                            item_path,
                                        )
                                    ),
                                    "_full_configuration": (
                                            full_configuration or {}
                                    ),
                                },
                            )

                        self._discover_blocks(
                            value=item,
                            current_path=item_path,
                            resource_type=resource_type,
                            resource_name=resource_name,
                            output=output,
                            full_configuration=full_configuration,
                        )

    def _looks_like_configuration_block(
            self,
            block_name: str,
            value: Any,
    ) -> bool:

        block_name = (
            self._clean_string(
                block_name
            ).lower()
        )

        if block_name in self.STRUCTURAL_BLOCK_NAMES:
            return True

        keywords = (
            "rule",
            "security",
            "network",
            "profile",
            "configuration",
            "policy",
            "ip_",
            "disk",
            "identity",
            "diagnostic",
            "firewall",
            "backend",
            "frontend",
        )

        if any(
                keyword in block_name
                for keyword in keywords
        ):
            return True

        if isinstance(value, dict):

            keys = {
                str(k).lower()
                for k in value.keys()
            }

            security_keys = {
                "direction",
                "access",
                "protocol",
                "source_address_prefix",
                "source_address_prefixes",
                "destination_address_prefix",
                "destination_address_prefixes",
                "source_port_range",
                "source_port_ranges",
                "destination_port_range",
                "destination_port_ranges",
                "priority",
            }

            if len(
                    keys.intersection(
                        security_keys
                    )
            ) >= 2:
                return True

        return False

    def _count_leaves(
            self,
            value: Any,
    ) -> int:

        if isinstance(value, dict):
            return sum(
                self._count_leaves(v)
                for v in value.values()
            )

        if isinstance(value, list):
            return sum(
                self._count_leaves(v)
                for v in value
            )

        return 1

    def _find_resource(
            self,
            infrastructure: Dict[str, Any],
            resource_type: str,
            resource_name: str,
    ) -> Optional[Dict[str, Any]]:

        for resource in infrastructure.get(
                "resources",
                [],
        ):

            if not isinstance(resource, dict):
                continue

            if (
                    self._clean_string(
                        resource.get("type")
                    ) == resource_type
                    and
                    self._clean_string(
                        resource.get("name")
                    ) == resource_name
            ):
                return resource

        return None

    def _relative_resource_path(
            self,
            path: str,
            resource_type: str,
            resource_name: str,
    ) -> str:

        prefix = (
            f"{resource_type}.{resource_name}"
        )

        if path == prefix:
            return ""

        if path.startswith(prefix + "."):
            return path[len(prefix) + 1:]

        return ""

    def _resolve_terraform_path(
            self,
            configuration: Any,
            relative_path: str,
    ) -> Any:

        if relative_path == "":
            return configuration

        current = configuration

        tokens = re.findall(
            r"([A-Za-z0-9_-]+)|\[(\d+)\]",
            relative_path,
        )

        for key_token, index_token in tokens:

            if key_token:

                if (
                        not isinstance(current, dict)
                        or key_token not in current
                ):
                    return None

                current = current[key_token]

            else:

                if not isinstance(current, list):
                    return None

                index = int(index_token)

                if (
                        index < 0
                        or index >= len(current)
                ):
                    return None

                current = current[index]

        return current

    # ==============================================================
    # RETRIEVAL
    # ==============================================================

    async def _retrieve_property_evidence(
            self,
            candidate: Dict[str, Any],
            existing_documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        path = self._clean_string(
            candidate["terraform_path"]
        )

        exact = []

        for doc in existing_documents:

            if not isinstance(doc, dict):
                continue

            query_type = self._clean_string(
                doc.get(
                    "query_type",
                    doc.get(
                        "_retrieval_query_type",
                        "",
                    ),
                )
            )

            doc_path = self._clean_string(
                doc.get(
                    "terraform_path",
                    doc.get(
                        "_terraform_path",
                        doc.get(
                            "terraform_path_id",
                            "",
                        ),
                    ),
                )
            )

            if (
                    query_type == "terraform_property"
                    and doc_path == path
            ):
                exact.append(doc)

        if exact:
            return self._deduplicate_documents(
                exact
            )

        if self.retriever_service is None:
            return []

        resource_type = self._clean_string(
            candidate["resource_type"]
        )

        property_name = self._clean_string(
            candidate["property"]
        )

        queries = [
            (
                f"Azure {resource_type} "
                f"{property_name} security requirement"
            ),
            (
                f"Azure {resource_type} "
                f"{property_name} recommended configuration"
            ),
            (
                f"Azure {property_name} "
                f"security configuration"
            ),
        ]

        # Targeted queries for specific properties
        if (
                resource_type == "azurerm_storage_account"
                and property_name == "https_traffic_only_enabled"
        ):
            queries.extend(
                [
                    "Azure Storage secure transfer required",
                    "Azure Storage HTTPS only",
                    "Azure Storage secure transfer HTTPS",
                    "Azure Storage account HTTPS security requirement",
                ]
            )

        if (
                resource_type == "azurerm_kubernetes_cluster"
                and property_name == "role_based_access_control_enabled"
        ):
            queries.extend(
                [
                    "Azure Kubernetes Service RBAC authorization security",
                    "AKS role based access control security requirement",
                    "Azure Kubernetes control plane authorization RBAC",
                ]
            )

        if (
                resource_type == "azurerm_kubernetes_cluster"
                and property_name == "network_policy"
        ):
            queries.extend(
                [
                    "AKS network policy pod isolation security",
                    "Azure Kubernetes network policy security",
                ]
            )

        if (
                resource_type == "azurerm_linux_virtual_machine"
                and property_name == "disable_password_authentication"
        ):
            queries.extend(
                [
                    "Azure Linux VM disable password authentication SSH",
                    "Azure Linux virtual machine SSH password authentication security",
                ]
            )

        if resource_type == "azurerm_key_vault":
            if property_name == "purge_protection_enabled":
                queries.extend(
                    [
                        "Azure Key Vault purge protection security",
                        "Azure Key Vault permanent deletion protection",
                    ]
                )
            elif property_name == "soft_delete_retention_days":
                queries.extend(
                    [
                        "Azure Key Vault soft delete retention security",
                        "Azure Key Vault retention period deleted secrets",
                    ]
                )

        if (
                resource_type == "azurerm_mssql_server"
                and property_name == "public_network_access_enabled"
        ):
            queries.extend(
                [
                    "Azure SQL Server public network access security",
                    "Azure SQL logical server public network access",
                ]
            )

        if (
                resource_type == "azurerm_app_service"
                and property_name == "https_only"
        ):
            queries.extend(
                [
                    "Azure App Service HTTPS only security",
                    "Azure Web App HTTPS only requirement",
                ]
            )

        retrieved = []

        for query in queries:

            try:

                results = (
                    await self.retriever_service.retrieve(
                        query=query,
                        top_k=10,
                    )
                )

                if results:
                    retrieved.extend(results)

            except Exception as exc:

                logger.warning(
                    "Property retrieval failed | %s | %s",
                    path,
                    exc,
                )

        return self._deduplicate_documents(
            retrieved
        )


    async def _retrieve_configuration_evidence(
            self,
            candidate: Dict[str, Any],
            existing_documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Retrieve evidence documents for a configuration block.

        This function merges:
        1. Direct configuration documents (query_type == "terraform_configuration")
        2. Property documents (query_type == "terraform_property") whose path
           starts with the configuration path (nested children)

        This is critical for configurations like network_profile[0] where evidence
        comes from child properties like network_plugin and network_policy.
        """
        target_path = self._clean_string(
            candidate.get("configuration_path")
            or candidate.get("terraform_path")
            or ""
        )

        if not target_path:
            logger.warning("No target path for configuration evidence retrieval")
            return []

        resource_type = self._clean_string(candidate.get("resource_type", ""))
        resource_name = self._clean_string(candidate.get("resource_name", ""))

        direct_documents: List[Dict[str, Any]] = []
        child_documents: List[Dict[str, Any]] = []

        # Build the prefix for child property matching
        prefix = target_path + "."

        logger.info(
            "CONFIG RETRIEVAL START | target=%s | total_documents=%d",
            target_path,
            len(existing_documents),
        )

        config_count = 0
        property_count = 0
        matching_property_count = 0

        for idx, document in enumerate(existing_documents):
            if not isinstance(document, dict):
                continue

            doc_path = self._clean_string(
                document.get("terraform_path")
                or document.get("_terraform_path")
                or document.get("terraform_path_id")
                or ""
            )

            config_path = self._clean_string(
                document.get("configuration_path")
                or ""
            )

            query_type = self._clean_string(
                document.get("query_type")
                or document.get("_retrieval_query_type")
                or ""
            )

            # Log AKS documents specifically for debugging
            if "aks" in doc_path.lower() and "network_profile" in doc_path.lower():
                logger.info(
                    "AKS DOC IN RETRIEVAL | idx=%d | query_type=%s | doc_path=%s",
                    idx,
                    query_type,
                    doc_path,
                )

            # ---------------------------------------------------------
            # Direct configuration evidence
            # ---------------------------------------------------------
            if query_type == "terraform_configuration":
                config_count += 1
                if doc_path == target_path or config_path == target_path:
                    direct_documents.append(document)
                    logger.info(
                        "DIRECT CONFIG DOC FOUND | idx=%d | doc_path=%s",
                        idx,
                        doc_path,
                    )
                continue

            # ---------------------------------------------------------
            # Nested property evidence
            # ---------------------------------------------------------
            if query_type == "terraform_property":
                property_count += 1

                # Method 1: exact prefix match
                if doc_path.startswith(prefix):
                    matching_property_count += 1
                    child_documents.append(document)
                    logger.info(
                        "CHILD MATCH (prefix) | idx=%d | doc_path=%s",
                        idx,
                        doc_path,
                    )
                    continue

                # Method 2: check if target_path is a parent of doc_path
                if target_path in doc_path and doc_path != target_path:
                    remaining = doc_path[len(target_path):]
                    if remaining.startswith(".") and "." not in remaining[1:]:
                        matching_property_count += 1
                        child_documents.append(document)
                        logger.info(
                            "CHILD MATCH (contains) | idx=%d | doc_path=%s",
                            idx,
                            doc_path,
                        )
                        continue

        logger.info(
            "CONFIG RETRIEVAL STATS | target=%s | config_docs=%d | property_docs=%d | matching_children=%d",
            target_path,
            config_count,
            property_count,
            matching_property_count,
        )

        # -------------------------------------------------------------
        # Merge and deduplicate
        # -------------------------------------------------------------

        result: List[Dict[str, Any]] = []
        seen: Set[Tuple[str, str, str, str]] = set()

        for document in direct_documents + child_documents:
            content = str(document.get("content", "")).strip()
            source = str(document.get("source", "")).strip()
            page = str(document.get("page", "")).strip()
            path = str(document.get("terraform_path", "")).strip()

            if not content:
                continue

            key = (source, page, path, content[:500])

            if key in seen:
                continue

            seen.add(key)
            result.append(document)

        logger.info(
            "CONFIGURATION EVIDENCE POOLS | path=%s | "
            "parent=%d | children=%d | total=%d",
            target_path,
            len(direct_documents),
            len(child_documents),
            len(result),
        )

        return result

    # ==============================================================
    # EVIDENCE EXTRACTION - PROPERTY
    # ==============================================================

    async def _extract_property_evidence(
            self,
            candidate: Dict[str, Any],
            documents: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:

        for index, document in enumerate(
                documents,
                start=1,
        ):

            content = str(
                document.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            quote = (
                await self._extract_exact_property_evidence(
                    candidate,
                    document,
                )
            )

            if (
                    quote
                    and self._evidence_quote_exists(
                quote,
                content,
            )
            ):
                return {
                    "document_index": index,
                    "document": document,
                    "quote": quote,
                }

        return None

    async def _extract_exact_property_evidence(
            self,
            candidate: Dict[str, Any],
            document: Dict[str, Any],
    ) -> Optional[str]:

        content = str(
            document.get(
                "content",
                "",
            )
        ).strip()

        if not content:
            return None

        resource_type = candidate.get("resource_type")
        property_name = candidate.get("property")
        path = candidate.get("terraform_path")
        value = candidate.get("observed_value")

        if not resource_type or not property_name or not path:
            return None

        value = self._safe_observed_value(
            value,
            path,
        )

        prompt = f"""
You are an exact Azure documentation evidence extractor.

Terraform resource type:
{resource_type}

Terraform property:
{property_name}

Terraform path:
{path}

Observed value:
{json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )}

AZURE DOCUMENT:
{content[:self.EVIDENCE_DOCUMENT_CHARS]}

TASK:

Extract ONE exact passage that DIRECTLY constrains the SAME
Azure service and SAME security/configuration concept.

The evidence MUST:
1. Apply to the same Azure service.
2. Apply to the same property/configuration concept.
3. Explicitly state a security or configuration requirement.

Reject:
- generic cloud advice
- unrelated services
- unrelated controls
- indirect inference
- Terraform comments
- assumptions
- unrelated recommendations

Copy the passage EXACTLY.

Return JSON only:

{{
  "evidence_quote": "EXACT COPIED TEXT"
}}

or:

{{
  "evidence_quote": null
}}
"""

        try:

            response = await self.llm_service.generate(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract exact Azure evidence only. "
                            "Never invent or paraphrase. "
                            "Return JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0,
                max_tokens=self.EVIDENCE_MAX_TOKENS,
                json_mode=True,
            )

            result = self._parse_single_json_object(
                response
            )

        except Exception:

            logger.exception(
                "Property evidence extraction failed | %s",
                path,
            )

            return None

        quote = self._clean_string(
            result.get("evidence_quote")
        )

        if not quote:
            return None

        return self._resolve_quote_in_document(
            quote,
            content,
        )

    # ==============================================================
    # EVIDENCE EXTRACTION - CONFIGURATION
    # ==============================================================

    async def _extract_configuration_evidence(
            self,
            candidate: Dict[str, Any],
            documents: List[Dict[str, Any]],
            terraform_catalog: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Extract evidence for a nested configuration block.

        Parent configuration documents are attempted first. When the parent
        block cannot yield a direct quote, evidence from directly nested
        Terraform properties is promoted to the parent configuration. This
        keeps the validator evidence-grounded while avoiding the failure mode
        where a parent block has many documents but the LLM returns null.
        """
        evidence_items: List[Dict[str, Any]] = []

        path = self._clean_string(candidate.get("configuration_path"))
        resource_type = self._clean_string(candidate.get("resource_type"))
        resource_name = self._clean_string(candidate.get("resource_name"))

        relative_config = self._relative_resource_path(
            path, resource_type, resource_name
        )

        exact_documents: List[Dict[str, Any]] = []
        child_property_documents: List[Dict[str, Any]] = []

        logger.info(
            "EXTRACT CONFIG START | path=%s | docs_count=%d | relative_config=%s",
            path,
            len(documents),
            relative_config,
        )

        # Separate documents into exact parent configs and child property docs
        for idx, document in enumerate(documents):
            if not isinstance(document, dict):
                continue

            query_type = self._clean_string(
                document.get(
                    "query_type",
                    document.get("_retrieval_query_type", ""),
                )
            )

            doc_path = self._clean_string(
                document.get(
                    "terraform_path",
                    document.get(
                        "_terraform_path",
                        document.get("terraform_path_id", ""),
                    ),
                )
            )

            if query_type == "terraform_configuration" and doc_path == path:
                exact_documents.append(document)
                logger.info("EXACT CONFIG DOC | idx=%d | path=%s", idx, doc_path)
                continue

            if query_type == "terraform_property":
                # Check if this property is a child of the configuration
                # using doc_path.startswith(path + ".")
                if doc_path.startswith(path + "."):
                    child_property_documents.append(document)
                    logger.info("CHILD PROPERTY DOC (startswith) | idx=%d | path=%s", idx, doc_path)
                    continue

                # Also check via relative path if available
                if relative_config:
                    doc_resource_type, doc_resource_name = self._extract_resource_identity(doc_path)
                    if doc_resource_type == resource_type and doc_resource_name == resource_name:
                        relative_property = self._relative_resource_path(
                            doc_path, resource_type, resource_name
                        )
                        if relative_property and relative_property.startswith(relative_config + "."):
                            child_property_documents.append(document)
                            logger.info("CHILD PROPERTY DOC (relative) | idx=%d | path=%s", idx, doc_path)
                            continue

        exact_documents = self._rank_documents(exact_documents)
        child_property_documents = self._rank_documents(
            child_property_documents
        )

        logger.info(
            "CONFIG EVIDENCE POOLS | path=%s | parent=%d | children=%d",
            path,
            len(exact_documents),
            len(child_property_documents),
        )

        # ==========================================================
        # 1. DIRECT PARENT CONFIGURATION EVIDENCE
        # ==========================================================
        for index, document in enumerate(
                exact_documents[: self.MAX_DOCUMENTS_PER_CONFIGURATION],
                start=1,
        ):
            if len(evidence_items) >= self.MAX_CONFIGURATION_EVIDENCE_ITEMS:
                break

            content = str(document.get("content", "")).strip()
            if not content:
                continue

            quote = await self._extract_exact_configuration_evidence(
                candidate=candidate,
                document=document,
            )

            if not quote or not self._evidence_quote_exists(quote, content):
                continue

            # Deduplication
            duplicate = any(
                self._normalize_text(item.get("quote", ""))
                == self._normalize_text(quote)
                for item in evidence_items
            )
            if duplicate:
                continue

            evidence_items.append(
                {
                    "document_index": index,
                    "document": document,
                    "quote": quote,
                    "source": self._clean_string(document.get("source")),
                    "page": self._clean_string(document.get("page")),
                    "evidence_scope": "configuration",
                    "evidence_path": path,
                }
            )

            logger.info(
                "CONFIGURATION EVIDENCE ITEM | path=%s | scope=configuration | source=%s | page=%s",
                path,
                evidence_items[-1]["source"],
                evidence_items[-1]["page"],
            )

        # ==========================================================
        # 2. CHILD-PROPERTY EVIDENCE PROMOTION
        # ==========================================================

        # For each child property document, extract evidence directly
        # We do NOT apply the Python relevance filter here; let the LLM decide.
        for index, document in enumerate(
                child_property_documents[: self.MAX_DOCUMENTS_PER_CONFIGURATION],
                start=1,
        ):
            if len(evidence_items) >= self.MAX_CONFIGURATION_EVIDENCE_ITEMS:
                break

            content = str(document.get("content", "")).strip()
            if not content:
                continue

            child_path = self._clean_string(
                document.get(
                    "terraform_path",
                    document.get(
                        "_terraform_path",
                        document.get("terraform_path_id", ""),
                    ),
                )
            )

            if not child_path:
                continue

            # Extract the child property name from the path
            if relative_config:
                relative_child = self._relative_resource_path(
                    child_path, resource_type, resource_name
                )
                if relative_child and relative_child.startswith(relative_config + "."):
                    child_property = relative_child[len(relative_config) + 1:]
                else:
                    child_property = child_path.split(".")[-1]
            else:
                child_property = child_path.split(".")[-1]

            # Build a child candidate for evidence extraction
            child_candidate = {
                "resource_type": resource_type,
                "resource_name": resource_name,
                "terraform_path": child_path,
                "property": child_property,
                "observed_value": self._resolve_terraform_path(
                    candidate.get("_full_configuration", {}),
                    relative_config + "." + child_property if relative_config else child_property
                ),
                "value_source": "terraform_explicit",
            }

            # Extract exact quote using the LLM (it will reject irrelevant content)
            quote = await self._extract_exact_property_evidence(
                child_candidate,
                document,
            )

            if not quote or not self._evidence_quote_exists(quote, content):
                continue

            # Deduplication
            duplicate = any(
                self._normalize_text(item.get("quote", ""))
                == self._normalize_text(quote)
                for item in evidence_items
            )
            if duplicate:
                continue

            item = {
                "document_index": index,
                "document": document,
                "quote": quote,
                "source": self._clean_string(document.get("source")),
                "page": self._clean_string(document.get("page")),
                "evidence_scope": "nested_property",
                "evidence_path": child_path,
                "parent_configuration_path": path,
                "child_property": child_property,
                "child_observed_value": child_candidate.get("observed_value"),
            }
            evidence_items.append(item)

            logger.info(
                "CHILD CONFIGURATION EVIDENCE ITEM | parent=%s | child=%s | source=%s | page=%s",
                path,
                child_path,
                item["source"],
                item["page"],
            )

        # ==========================================================
        # RESULT
        # ==========================================================
        if not evidence_items:
            logger.warning(
                "NO CONFIGURATION EVIDENCE | path=%s",
                path,
            )
            return None

        return {
            "items": evidence_items,
            "quotes": [
                item["quote"]
                for item in evidence_items
                if item.get("quote")
            ],
            "documents": [
                item["document"]
                for item in evidence_items
                if item.get("document")
            ],
        }

    def _build_child_property_candidate(
            self,
            parent_candidate: Dict[str, Any],
            child_path: str,
    ) -> Optional[Dict[str, Any]]:
        """Build a synthetic child-property candidate for evidence extraction.

        This candidate is used only to identify the exact child concept. It is
        never independently emitted as a finding by this configuration path.
        """
        parent_path = self._clean_string(
            parent_candidate.get("configuration_path")
        )
        child_path = self._clean_string(child_path)
        resource_type = self._clean_string(
            parent_candidate.get("resource_type")
        )
        resource_name = self._clean_string(
            parent_candidate.get("resource_name")
        )

        if not parent_path or not child_path or not resource_type or not resource_name:
            return None

        prefix = f"{resource_type}.{resource_name}"
        if not child_path.startswith(prefix + "."):
            return None

        relative_parent = self._relative_resource_path(
            parent_path, resource_type, resource_name
        )
        relative_child = self._relative_resource_path(
            child_path, resource_type, resource_name
        )

        if not relative_parent or not relative_child.startswith(
                relative_parent + "."
        ):
            return None

        nested_path = relative_child[len(relative_parent) + 1:]
        if not nested_path:
            return None

        property_name = nested_path.split(".")[-1]

        full_configuration = parent_candidate.get(
            "_full_configuration",
            {},
        )
        observed = self._resolve_terraform_path(
            full_configuration,
            relative_child,
        )

        return {
            "resource_type": resource_type,
            "resource_name": resource_name,
            "terraform_path": child_path,
            "property": property_name,
            "observed_value": observed,
            "value_source": "terraform_explicit",
        }

    async def _extract_exact_configuration_evidence(
            self,
            candidate: Dict[str, Any],
            document: Dict[str, Any],
    ) -> Optional[str]:

        content = str(
            document.get(
                "content",
                "",
            )
        ).strip()

        if not content:
            return None

        path = candidate["configuration_path"]
        resource_type = candidate["resource_type"]
        resource_name = candidate["resource_name"]
        observed = candidate["observed_value"]

        prompt = f"""
You are an exact Azure documentation evidence extractor.

Azure resource type:
{resource_type}

Azure resource name:
{resource_name}

Terraform configuration path:
{path}

Observed configuration:
{json.dumps(
            observed,
            ensure_ascii=False,
            indent=2,
            default=str,
        )}

AZURE DOCUMENT:
{content[:self.CONFIGURATION_DOCUMENT_CHARS]}

TASK:

Extract ONE exact passage that directly supports a security
or configuration requirement relevant to this SAME Azure
service and this SAME configuration block.

The passage may describe:
1. the complete nested block, OR
2. one security-sensitive field inside this exact block.

For an NSG security_rule, the relevant fields can include:
- direction
- access
- protocol
- source_port_range
- destination_port_range
- source_address_prefix
- destination_address_prefix
- priority

The passage must establish an actual requirement.
Do not infer a rule from generic terminology.

Reject:
- unrelated services
- unrelated controls
- generic cloud advice
- "inbound" by itself
- "allow" by itself
- "*" by itself
- "address" by itself
- "range" by itself
- Terraform comments
- indirect assumptions
- cross-service inference

Example:
"Don't assign allow rules with broad ranges"
may be evidence for an NSG security_rule with a broad
source/destination rule.

It is NOT evidence that a virtual network
address_space such as 10.0.0.0/16 is insecure.

Copy the passage EXACTLY from the document.

Return JSON only:

{{
  "evidence_quote": "EXACT COPIED TEXT"
}}

or:

{{
  "evidence_quote": null
}}
"""

        try:
            response = await self.llm_service.generate(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Extract exact Azure configuration "
                            "evidence only. Never invent. "
                            "Never paraphrase. "
                            "Return JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0,
                max_tokens=self.EVIDENCE_MAX_TOKENS,
                json_mode=True,
            )

            result = self._parse_single_json_object(
                response
            )

        except Exception:
            logger.exception(
                "Configuration evidence extraction failed | %s",
                path,
            )
            return None

        quote = self._clean_string(
            result.get("evidence_quote")
        )

        if not quote:
            return None

        return self._resolve_quote_in_document(
            quote,
            content,
        )

    # ==============================================================
    # PROPERTY EVIDENCE RELEVANCE - 3-LEVEL SEMANTIC MATCHING
    # ==============================================================

    def _property_evidence_is_relevant(
            self,
            candidate: Dict[str, Any],
            evidence_quote: str,
    ) -> bool:
        """
        Check that the evidence quote is semantically relevant to the property.

        Uses a 3-level semantic matching approach:
        Level 1: Resource type match (e.g., "storage account" for azurerm_storage_account)
        Level 2: Property semantic match (e.g., "TLS 1.2" for min_tls_version)
        Level 3: Security context match (optional, reinforces the match)

        The key principle: Azure documentation uses natural language,
        not Terraform property names.
        """
        property_name = self._clean_string(
            candidate.get("property")
        ).lower()
        resource_type = self._clean_string(
            candidate.get("resource_type")
        ).lower()

        quote = self._normalize_text(evidence_quote)
        if not property_name or not quote:
            return False

        # ==========================================================
        # SPECIAL CASES - VNet address_space protection
        # ==========================================================

        # VNet address-space protection: NSG allow-rule evidence is not
        # evidence for a VNet CIDR configuration.
        if (
                resource_type == "azurerm_virtual_network"
                and property_name.startswith("address_space")
        ):
            nsgrule_terms = (
                "allow rules",
                "security rule",
                "network security group",
                "nsg",
                "source address",
                "destination address",
                "source port",
                "destination port",
                "security rule",
                "inbound traffic",
                "outbound traffic",
            )
            vnet_terms = (
                "virtual network address space",
                "address space",
                "vnet address",
                "subnet address space",
                "address prefix",
                "cidr",
            )

            # If it's about NSG rules but NOT about VNet address space, reject
            if (
                    not any(term in quote for term in vnet_terms)
                    and any(term in quote for term in nsgrule_terms)
            ):
                return False

        # ==========================================================
        # LEVEL 1: RESOURCE TYPE MATCH
        # ==========================================================

        resource_aliases = self.RESOURCE_ALIASES.get(resource_type, [])
        if not resource_aliases:
            # If no resource aliases defined, fall back to property matching only
            logger.debug(
                "No resource aliases for %s, proceeding with property match",
                resource_type
            )
        else:
            resource_match = any(
                alias in quote
                for alias in resource_aliases
            )
            if not resource_match:
                # For some generic properties, resource match might be too strict
                # Check if this is a property that's commonly discussed without resource name
                generic_properties = {"min_tls_version", "https_only", "purge_protection_enabled"}
                if property_name not in generic_properties:
                    logger.debug(
                        "No resource match | resource=%s | aliases=%s | quote=%s",
                        resource_type,
                        resource_aliases[:3],
                        quote[:100]
                    )
                    # Still allow if property match is strong
                    # We'll continue to property matching anyway (don't return False yet)
                # else: proceed to property matching

        # ==========================================================
        # LEVEL 2: PROPERTY SEMANTIC MATCH
        # ==========================================================

        property_aliases = self.PROPERTY_ALIASES.get(property_name, [])
        if not property_aliases:
            # Fall back to exact property name matching
            property_match = property_name in quote
        else:
            property_match = any(
                alias in quote
                for alias in property_aliases
            )

        if not property_match:
            # Special case: for min_tls_version, look for TLS mentions
            if property_name == "min_tls_version":
                property_match = (
                        "tls 1.2" in quote
                        or "minimum tls" in quote
                        or "tls1.2" in quote
                )
            # Special case: for public_network_access_enabled
            elif property_name == "public_network_access_enabled":
                property_match = (
                        "public network access" in quote
                        or "public access" in quote
                        or "disable public" in quote
                        or "block public" in quote
                )
            # Special case: for disable_password_authentication
            elif property_name == "disable_password_authentication":
                property_match = (
                        "password authentication" in quote
                        or "disable password" in quote
                        or "ssh password" in quote
                        or "ssh key" in quote
                )
            # Special case: for network_policy - look for network policy terms
            elif property_name == "network_policy":
                property_match = (
                        "network policy" in quote
                        or "network policies" in quote
                        or "pod isolation" in quote
                        or "traffic policy" in quote
                )
            # Special case: for network_plugin
            elif property_name == "network_plugin":
                property_match = (
                        "network plugin" in quote
                        or "networking plugin" in quote
                        or "container networking" in quote
                        or "azure cni" in quote
                        or "kubenet" in quote
                )
            # Special case: for https_traffic_only_enabled
            elif property_name == "https_traffic_only_enabled":
                property_match = (
                        "https only" in quote
                        or "secure transfer" in quote
                        or "encrypted transfer" in quote
                )
            # Special case: for soft_delete_retention_days
            elif property_name == "soft_delete_retention_days":
                property_match = (
                        "soft delete" in quote
                        or "retention days" in quote
                        or "retention period" in quote
                )
            # Special case: for purge_protection_enabled
            elif property_name == "purge_protection_enabled":
                property_match = (
                        "purge protection" in quote
                        or "purge-protection" in quote
                        or "deletion protection" in quote
                )
            # Special case: for https_only
            elif property_name == "https_only":
                property_match = (
                        "https only" in quote
                        or "https" in quote
                        or "secure http" in quote
                )

        if not property_match:
            logger.debug(
                "No property match | property=%s | aliases=%s | quote=%s",
                property_name,
                property_aliases[:3] if property_aliases else [],
                quote[:100]
            )
            return False

        # ==========================================================
        # LEVEL 3: SECURITY CONTEXT (optional reinforcement)
        # ==========================================================

        # Check for security context to reinforce the match
        security_terms = {
            "security",
            "secure",
            "protect",
            "enable",
            "disable",
            "require",
            "must",
            "should",
            "recommend",
            "best practice",
            "compliance",
            "control",
            "hardening",
        }

        has_security_context = any(
            term in quote
            for term in security_terms
        )

        # If we have resource + property match, it's sufficient even without security context
        # But log if we don't have security context for debugging
        if not has_security_context:
            logger.debug(
                "No security context in quote | property=%s | quote=%s",
                property_name,
                quote[:100]
            )

        # ==========================================================
        # SPECIAL HANDLING FOR SPECIFIC RESOURCE/PROPERTY PAIRS
        # ==========================================================

        # For storage account properties, ensure we have storage context
        if resource_type == "azurerm_storage_account":
            storage_context = any(
                term in quote
                for term in ["storage", "account", "blob", "container"]
            )
            if not storage_context and property_name not in {"min_tls_version"}:
                # Allow if property match is strong
                pass

        # For AKS properties - make this more lenient
        if resource_type == "azurerm_kubernetes_cluster":
            aks_context = any(
                term in quote
                for term in ["kubernetes", "aks", "cluster", "k8s", "aks cluster", "azure kubernetes"]
            )
            # Don't require AKS context for network properties as they might be in network docs
            if not aks_context and property_name not in {"network_policy", "network_plugin"}:
                # Still allow if property match is strong
                pass

        # For Key Vault properties
        if resource_type == "azurerm_key_vault":
            kv_context = any(
                term in quote
                for term in ["key vault", "vault", "secrets", "keys"]
            )
            if not kv_context and property_name not in {"purge_protection_enabled", "soft_delete_retention_days"}:
                pass

        # For Linux VM
        if resource_type == "azurerm_linux_virtual_machine":
            vm_context = any(
                term in quote
                for term in ["virtual machine", "linux vm", "vm", "linux"]
            )
            if not vm_context and property_name not in {"disable_password_authentication"}:
                pass

        return True

    # ==============================================================
    # ANALYSIS - PROPERTY
    # ==============================================================

    async def _analyze_property(
            self,
            candidate: Dict[str, Any],
            documents: List[Dict[str, Any]],
            evidence_quote: str,
            document: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        path = candidate[
            "terraform_path"
        ]

        if not self._validate_evidence_quote(
                evidence_quote,
                documents,
        ):
            return None

        content = str(
            document.get(
                "content",
                "",
            )
        ).strip()

        value = self._safe_observed_value(
            candidate["observed_value"],
            path,
        )

        prompt = f"""
You are a STRICT evidence-grounded Terraform/Azure auditor.

RESOURCE TYPE:
{candidate["resource_type"]}

RESOURCE NAME:
{candidate["resource_name"]}

PROPERTY:
{candidate["property"]}

TERRAFORM PATH:
{path}

OBSERVED VALUE:
{json.dumps(
            value,
            ensure_ascii=False,
            default=str,
        )}

VERIFIED AZURE EVIDENCE:
{evidence_quote}

SOURCE DOCUMENT:
{content[:self.FINDING_DOCUMENT_CHARS]}

TASK:

Determine whether the observed Terraform value violates the
requirement DIRECTLY established by the verified evidence.

The evidence must apply to the SAME Azure service and SAME
property/configuration concept.

Do NOT invent:
- requirements
- operators
- expected values
- severities
- remediation
- cross-service mappings

IMPORTANT:

The operator describes the DOCUMENTED COMPLIANCE CONDITION.

Examples:

HTTPS must be enabled:
operator="eq"
expected_value=true

Public network access must be disabled:
operator="eq"
expected_value=false

Minimum TLS must be TLS1_2:
operator="gte"
expected_value="TLS1_2"

Do NOT use "neq" for minimum-version requirements.

Return JSON ONLY.

VIOLATION:

{{
  "supported": true,
  "violated": true,
  "requirement": "Direct documented requirement",
  "problem": "Specific Terraform violation",
  "why_it_matters": "Impact supported by evidence",
  "recommendation": "Specific remediation",
  "severity": "High",
  "operator": "eq",
  "expected_value": false
}}

COMPLIANT:

{{
  "supported": true,
  "violated": false,
  "reason": "Terraform satisfies the documented requirement"
}}

UNSUPPORTED:

{{
  "supported": false,
  "violated": false,
  "reason": "Evidence does not apply to this property"
}}
"""

        try:

            response = await self.llm_service.generate(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Strict evidence-grounded validator. "
                            "Use only supplied evidence. "
                            "Return JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0,
                max_tokens=self.FINDING_MAX_TOKENS,
                json_mode=True,
            )

            result = self._parse_single_json_object(
                response
            )

        except Exception:

            logger.exception(
                "Property analysis failed | %s",
                path,
            )

            return None

        if not bool(
                result.get("supported", False)
        ):
            return {
                "_analysis_status": "unsupported"
            }

        if not bool(
                result.get("violated", False)
        ):
            return {
                "_analysis_status": "compliant"
            }

        finding = self._parse_finding_result(
            result=result,
            evidence_quote=evidence_quote,
            path=path,
            require_operator=True,
        )

        if not finding:
            return None

        finding["_analysis_status"] = "violation"

        return finding

    # ==============================================================
    # ANALYSIS - CONFIGURATION
    # ==============================================================

    async def _analyze_configuration(
            self,
            candidate: Dict[str, Any],
            documents: List[Dict[str, Any]],
            evidence: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:

        path = candidate[
            "configuration_path"
        ]

        evidence_items = evidence.get(
            "items",
            [],
        )

        if not evidence_items:
            return None

        observed = candidate[
            "observed_value"
        ]

        # ----------------------------------------------------------
        # Build compact multi-source evidence
        # ----------------------------------------------------------

        evidence_sections = []

        for index, item in enumerate(
                evidence_items,
                start=1,
        ):

            source = self._clean_string(
                item.get("source")
            )

            page = self._clean_string(
                item.get("page")
            )

            quote = self._clean_string(
                item.get("quote")
            )

            evidence_sections.append(
                f"""
EVIDENCE #{index}
Source: {source}
Page: {page}

{quote}
""".strip()
            )

        evidence_text = "\n\n".join(
            evidence_sections
        )

        # ----------------------------------------------------------
        # Source excerpts
        # ----------------------------------------------------------

        source_sections = []

        for index, item in enumerate(
                evidence_items,
                start=1,
        ):

            item_document = item.get(
                "document",
                {},
            )

            content = str(
                item_document.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            source_sections.append(
                f"""
SOURCE EXCERPT #{index}

{content[:6000]}
""".strip()
            )

        source_text = "\n\n".join(
            source_sections
        )

        prompt = f"""
You are a STRICT evidence-grounded Terraform/Azure configuration auditor.

RESOURCE TYPE:
{candidate["resource_type"]}

RESOURCE NAME:
{candidate["resource_name"]}

CONFIGURATION PATH:
{path}

OBSERVED CONFIGURATION:
{json.dumps(
            observed,
            ensure_ascii=False,
            indent=2,
            default=str,
        )}

VERIFIED AZURE EVIDENCE:
{evidence_text}

SOURCE EXCERPTS:
{source_text}

TASK:

Evaluate the COMPLETE Terraform configuration against the
verified Azure documentation.

IMPORTANT:

1. Use ONLY the supplied Azure evidence.
2. Evidence must apply to the SAME Azure service.
3. Evidence must apply to this SAME configuration block or
   one of its directly nested security-sensitive fields.
4. Do NOT infer undocumented security rules.
5. Do NOT combine unrelated controls.
6. Do NOT use Terraform knowledge that is absent from evidence.
7. A single field must NOT be considered vulnerable by itself
   when the documented requirement concerns the complete block.
8. If evidence concerns a child property, verify that the child
   property actually exists in the observed configuration.
9. Do not transform generic networking language into a finding.

For an NSG security rule, evaluate together:

- direction
- access
- protocol
- source ports
- destination ports
- source address
- destination address- priority

Examples:

Inbound alone is NOT a vulnerability.

Allow alone is NOT a vulnerability.

Wildcard "*" alone is NOT sufficient unless the supplied
documentation directly establishes the corresponding
security requirement.

The configuration is a violation only when the complete
observed configuration directly fails a documented requirement.

Return JSON ONLY.

VIOLATION:

{{
  "supported": true,
  "violated": true,
  "requirement": "Direct documented configuration requirement",
  "problem": "Specific configuration violation",
  "why_it_matters": "Impact supported by supplied evidence",
  "recommendation": "Specific remediation",
  "severity": "High"
}}

COMPLIANT:

{{
  "supported": true,
  "violated": false,
  "reason": "Configuration satisfies the documented requirement"
}}

UNSUPPORTED:

{{
  "supported": false,
  "violated": false,
  "reason": "The supplied evidence does not directly support a control for this configuration"
}}
"""

        try:

            response = await self.llm_service.generate(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a strict Azure configuration "
                            "auditor. Use only supplied evidence. "
                            "Never invent rules. "
                            "Return JSON only."
                        ),
                    },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                temperature=0,
                max_tokens=(
                    self.CONFIGURATION_FINDING_MAX_TOKENS
                ),
                json_mode=True,
            )

            result = self._parse_single_json_object(
                response
            )

        except Exception:

            logger.exception(
                "Configuration analysis failed | %s",
                path,
            )

            return None

        # ----------------------------------------------------------
        # UNSUPPORTED
        # ----------------------------------------------------------

        if not bool(
                result.get("supported", False)
        ):
            return {
                "_analysis_status": "unsupported"
            }

        # ----------------------------------------------------------
        # COMPLIANT
        # ----------------------------------------------------------

        if not bool(
                result.get("violated", False)
        ):
            return {
                "_analysis_status": "compliant"
            }

        # ----------------------------------------------------------
        # VIOLATION
        # ----------------------------------------------------------

        primary_quote = (
            evidence_items[0].get(
                "quote",
                "",
            )
        )

        finding = self._parse_finding_result(
            result=result,
            evidence_quote=primary_quote,
            path=path,
            require_operator=False,
        )

        if not finding:
            return None

        # Keep all evidence, not only the first quote.
        finding["evidence_quotes"] = [
            item.get(
                "quote",
                "",
            )
            for item in evidence_items
            if item.get("quote")
        ]

        finding["evidence_sources"] = [
            {
                "source": item.get(
                    "source",
                    "",
                ),
                "page": item.get(
                    "page",
                    "",
                ),
            }
            for item in evidence_items
        ]

        finding["_analysis_status"] = "violation"

        return finding

    # ==============================================================
    # FINDING PARSER
    # ==============================================================

    def _parse_finding_result(
            self,
            result: Dict[str, Any],
            evidence_quote: str,
            path: str,
            require_operator: bool,
    ) -> Optional[Dict[str, Any]]:

        if not result:
            return None

        if not bool(
                result.get(
                    "supported",
                    False,
                )
        ):
            return None

        if not bool(
                result.get(
                    "violated",
                    False,
                )
        ):
            return None

        requirement = self._clean_string(
            result.get("requirement")
        )

        problem = self._clean_string(
            result.get("problem")
        )

        why = self._clean_string(
            result.get("why_it_matters")
        )

        recommendation = self._clean_string(
            result.get("recommendation")
        )

        if (
                not requirement
                or not problem
                or not why
                or not recommendation
        ):
            logger.warning(
                "Finding rejected because required explanatory "
                "fields are missing | %s",
                path,
            )
            return None

        severity = self._strict_severity(
            result.get("severity")
        )

        if severity is None:
            logger.warning(
                "Finding rejected because severity is invalid | %s | %s",
                path,
                result.get("severity"),
            )
            return None

        finding = {
            "supported": True,
            "violated": True,
            "rule": requirement,
            "requirement": requirement,
            "problem": problem,
            "why_it_matters": why,
            "impact": why,
            "recommendation": recommendation,
            "severity": severity,
            "evidence_quote": evidence_quote,
        }

        if require_operator:

            operator_raw = result.get(
                "operator"
            )

            expected_value = result.get(
                "expected_value"
            )

            if (
                    operator_raw is None
                    or expected_value is None
            ):
                logger.warning(
                    "Property finding rejected: "
                    "operator/expected_value missing | %s",
                    path,
                )
                return None

            operator = self._strict_operator(
                operator_raw
            )

            if operator is None:
                logger.warning(
                    "Property finding rejected: invalid operator | %s",
                    path,
                )
                return None

            finding["operator"] = operator
            finding["expected_value"] = (
                expected_value
            )

        return finding

    # ==============================================================
    # ACCEPTANCE
    # ==============================================================

    def _accept_finding(
            self,
            finding: Dict[str, Any],
            candidate: Dict[str, Any],
            documents: List[Dict[str, Any]],
            terraform_catalog: List[Dict[str, Any]],
            is_configuration: bool,
    ) -> bool:

        required_fields = (
            "supported",
            "violated",
            "rule",
            "problem",
            "why_it_matters",
            "recommendation",
            "severity",
        )

        for field in required_fields:

            if not finding.get(field):
                logger.warning(
                    "Finding rejected: missing field=%s",
                    field,
                )
                return False

        if not self._validate_resource_identity(
                finding,
                candidate,
        ):
            logger.warning(
                "Finding rejected: resource identity mismatch"
            )
            return False

        if not self._validate_terraform_identity(
                finding,
                candidate,
                terraform_catalog,
                is_configuration,
        ):
            logger.warning(
                "Finding rejected: Terraform identity mismatch"
            )
            return False

        if not self._validate_evidence_quote(
                finding.get(
                    "evidence_quote",
                    "",
                ),
                documents,
        ):
            logger.warning(
                "Finding rejected: primary evidence quote not found"
            )
            return False

        # ----------------------------------------------------------
        # Validate all configuration evidence too
        # ----------------------------------------------------------

        if is_configuration:

            evidence_quotes = finding.get(
                "evidence_quotes",
                [],
            )

            if not evidence_quotes:
                evidence_quotes = [
                    finding.get(
                        "evidence_quote",
                        "",
                    )
                ]

            for quote in evidence_quotes:

                if not self._validate_evidence_quote(
                        quote,
                        documents,
                ):
                    logger.warning(
                        "Configuration finding rejected: "
                        "secondary evidence quote not found"
                    )
                    return False

        # ----------------------------------------------------------
        # Property comparison
        # ----------------------------------------------------------

        if not is_configuration:

            if not self._validate_property_violation_logic(
                    finding,
                    candidate,
            ):
                logger.warning(
                    "Finding rejected: property logic mismatch"
                )
                return False

        return True

    def _validate_resource_identity(
            self,
            finding: Dict[str, Any],
            candidate: Dict[str, Any],
    ) -> bool:

        return (
                self._clean_string(
                    finding.get("resource")
                )
                ==
                self._clean_string(
                    candidate.get("resource_type")
                )
                and
                self._clean_string(
                    finding.get("resource_name")
                )
                ==
                self._clean_string(
                    candidate.get("resource_name")
                )
        )

    def _validate_terraform_identity(
            self,
            finding: Dict[str, Any],
            candidate: Dict[str, Any],
            terraform_catalog: List[Dict[str, Any]],
            is_configuration: bool,
    ) -> bool:

        path = self._clean_string(
            finding.get(
                "terraform_path"
            )
        )

        expected = (
            candidate.get(
                "configuration_path"
            )
            if is_configuration
            else candidate.get(
                "terraform_path"
            )
        )

        if not path or path != expected:
            return False

        if is_configuration:
            return True

        valid_paths = {
            self._clean_string(
                item.get(
                    "terraform_path"
                )
            )
            for item in terraform_catalog
        }

        if path in valid_paths:
            return True

        return (
                candidate.get("value_source")
                == "terraform_provider_default"
        )

    def _validate_property_violation_logic(
            self,
            finding: Dict[str, Any],
            candidate: Dict[str, Any],
    ) -> bool:

        expected = finding.get(
            "expected_value"
        )

        if expected is None:
            return False

        observed = candidate.get(
            "observed_value"
        )

        operator = self._strict_operator(
            finding.get(
                "operator"
            )
        )

        if operator is None:
            return False

        satisfies = self._generic_compare(
            observed=observed,
            operator=operator,
            expected=expected,
        )

        return not satisfies

    # ==============================================================
    # EVIDENCE VALIDATION
    # ==============================================================

    def _validate_evidence_quote(
            self,
            quote: str,
            documents: List[Dict[str, Any]],
    ) -> bool:

        quote = self._clean_string(
            quote
        )

        if not quote:
            return False

        for doc in documents:

            if not isinstance(doc, dict):
                continue

            content = str(
                doc.get(
                    "content",
                    "",
                )
            )

            if self._evidence_quote_exists(
                    quote,
                    content,
            ):
                return True

        return False

    def _evidence_quote_exists(
            self,
            quote: str,
            document: str,
    ) -> bool:

        if not quote or not document:
            return False

        q = self._normalize_text(
            quote
        )

        d = self._normalize_text(
            document
        )

        if q and q in d:
            return True

        q2 = re.sub(
            r"(?<=\w)-\s+",
            "",
            q,
        )

        d2 = re.sub(
            r"(?<=\w)-\s+",
            "",
            d,
        )

        return bool(
            q2 and q2 in d2
        )

    def _resolve_quote_in_document(
            self,
            quote: str,
            document: str,
    ) -> Optional[str]:

        if self._evidence_quote_exists(
                quote,
                document,
        ):
            return quote

        return None

    # ==============================================================
    # DOCUMENTS
    # ==============================================================

    def _select_documents(
            self,
            retrieved_documents: Optional[
                List[Dict[str, Any]]
            ],
            reranked_documents: Optional[
                List[Dict[str, Any]]
            ],
    ) -> List[Dict[str, Any]]:

        combined = []

        if isinstance(
                reranked_documents,
                list,
        ):
            combined.extend(
                reranked_documents
            )

        if isinstance(
                retrieved_documents,
                list,
        ):
            combined.extend(
                retrieved_documents
            )

        selected = []
        seen = set()

        for doc in combined:

            if not isinstance(doc, dict):
                continue

            content = str(
                doc.get(
                    "content",
                    "",
                )
            ).strip()

            if not content:
                continue

            source = self._clean_string(
                doc.get("source")
            )

            page = self._clean_string(
                doc.get("page")
            )

            query_type = self._clean_string(
                doc.get(
                    "query_type",
                    doc.get(
                        "_retrieval_query_type",
                        "",
                    ),
                )
            )

            terraform_path = self._clean_string(
                doc.get(
                    "terraform_path",
                    doc.get(
                        "_terraform_path",
                        doc.get(
                            "terraform_path_id",
                            "",
                        ),
                    ),
                )
            )

            key = (
                source,
                page,
                query_type,
                terraform_path,
                content[:800],
            )

            if key in seen:
                continue

            seen.add(key)

            enriched = dict(doc)

            if query_type:
                enriched["query_type"] = query_type

            if terraform_path:

                enriched["terraform_path"] = (
                    terraform_path
                )

                enriched["_terraform_path"] = (
                    terraform_path
                )

            selected.append(
                enriched
            )

        ranked = self._rank_documents(
            selected
        )

        logger.warning(
            "SELECTED DOCUMENTS=%d | configuration=%d | property=%d",
            len(ranked),
            sum(
                1
                for x in ranked
                if x.get(
                    "query_type"
                ) == "terraform_configuration"
            ),
            sum(
                1
                for x in ranked
                if x.get(
                    "query_type"
                ) == "terraform_property"
            ),
        )

        return ranked

    def _deduplicate_documents(
            self,
            documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        result = []
        seen = set()

        for doc in documents:

            if not isinstance(doc, dict):
                continue

            content = str(
                doc.get(
                    "content",
                    "",
                )
            ).strip()

            source = str(
                doc.get(
                    "source",
                    "",
                )
            ).strip()

            page = str(
                doc.get(
                    "page",
                    "",
                )
            ).strip()

            query_type = str(
                doc.get(
                    "query_type",
                    "",
                )
            ).strip()

            path = str(
                doc.get(
                    "terraform_path",
                    doc.get(
                        "_terraform_path",
                        "",
                    ),
                )
            ).strip()

            key = (
                source,
                page,
                query_type,
                path,
                content[:800],
            )

            if key in seen:
                continue

            seen.add(key)

            result.append(doc)

        return self._rank_documents(
            result
        )

    def _rank_documents(
            self,
            documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        valid = [
            doc
            for doc in documents
            if (
                    isinstance(doc, dict)
                    and str(
                doc.get(
                    "content",
                    "",
                )
            ).strip()
            )
        ]

        valid.sort(
            key=lambda doc: self._safe_numeric(
                doc.get(
                    "rerank_score",
                    doc.get(
                        "score",
                        -999999.0,
                    ),
                ),
                -999999.0,
            ),
            reverse=True,
        )

        return valid

    # ==============================================================
    # COVERAGE
    # ==============================================================

    def _coverage(
            self,
            evaluated_controls: Set[str],
            prefix: str,
            total: int,
    ) -> float:

        if total <= 0:
            return 0.0

        count = sum(
            1
            for x in evaluated_controls
            if x.startswith(prefix)
        )

        return count / total

    # ==============================================================
    # GENERIC COMPARISON
    # ==============================================================

    def _generic_compare(
            self,
            observed: Any,
            operator: str,
            expected: Any,
    ) -> bool:

        operator = self._strict_operator(
            operator
        )

        if operator is None:
            return False

        if isinstance(
                observed,
                str,
        ):
            observed = observed.strip()

        if isinstance(
                expected,
                str,
        ):
            expected = expected.strip()

        # ----------------------------------------------------------
        # BOOLEAN
        # ----------------------------------------------------------

        if (
                isinstance(observed, bool)
                or isinstance(expected, bool)
        ):

            if operator == "eq":
                return observed is expected

            if operator == "neq":
                return observed is not expected

            return False

        # ----------------------------------------------------------
        # TLS
        # ----------------------------------------------------------

        if (
                isinstance(observed, str)
                and isinstance(expected, str)
        ):

            observed_tls = (
                self._parse_tls_version(
                    observed
                )
            )

            expected_tls = (
                self._parse_tls_version(
                    expected
                )
            )

            if (
                    observed_tls is not None
                    and expected_tls is not None
            ):
                observed = observed_tls
                expected = expected_tls

        # ----------------------------------------------------------
        # CONTAINS
        # ----------------------------------------------------------

        if operator == "contains":
            return (
                    str(expected).lower()
                    in str(observed).lower()
            )

        if operator == "not_contains":
            return (
                    str(expected).lower()
                    not in str(observed).lower()
            )

        # ----------------------------------------------------------
        # IN / NOT IN
        # ----------------------------------------------------------

        if operator == "in":

            if isinstance(
                    expected,
                    list,
            ):
                return observed in expected

            return observed == expected

        if operator == "nin":

            if isinstance(
                    expected,
                    list,
            ):
                return observed not in expected

            return observed != expected

        # ----------------------------------------------------------
        # NUMERIC
        # ----------------------------------------------------------

        try:

            a = float(observed)
            b = float(expected)

            if operator == "eq":
                return a == b

            if operator == "neq":
                return a != b

            if operator == "gt":
                return a > b

            if operator == "gte":
                return a >= b

            if operator == "lt":
                return a < b

            if operator == "lte":
                return a <= b

        except (
                TypeError,
                ValueError,
        ):
            pass

        # ----------------------------------------------------------
        # STRING
        # ----------------------------------------------------------

        if operator == "eq":
            return (
                    str(observed).lower()
                    == str(expected).lower()
            )

        if operator == "neq":
            return (
                    str(observed).lower()
                    != str(expected).lower()
            )

        return False

    def _strict_operator(
            self,
            value: Any,
    ) -> Optional[str]:

        normalized = self._clean_string(
            value
        ).lower()

        if normalized not in self.VALID_OPERATORS:
            return None

        return normalized

    def _parse_tls_version(
            self,
            value: str,
    ) -> Optional[int]:

        if not isinstance(value, str):
            return None

        value = value.strip().upper()

        patterns = (
            r"TLS1[_\s\.]?(\d+)",
            r"TLS\s+1[_\s\.]?(\d+)",
            r"TLS(\d+)",
        )

        for pattern in patterns:

            match = re.search(
                pattern,
                value,
            )

            if match:

                try:
                    return int(
                        match.group(1)
                    )

                except ValueError:
                    return None

        return None

    # ==============================================================
    # HELPERS
    # ==============================================================

    def _extract_resource_identity(
            self,
            terraform_path: str,
    ) -> Tuple[str, str]:

        parts = str(
            terraform_path
        ).split(".")

        if len(parts) < 2:
            return "", ""

        return (
            self._clean_string(
                parts[0]
            ),
            self._clean_string(
                parts[1]
            ),
        )

    def _is_secret_property(
            self,
            terraform_path: str,
    ) -> bool:

        path = str(
            terraform_path
        ).lower()

        leaf = path.split(".")[-1]

        leaf = re.sub(
            r"\[\d+\]",
            "",
            leaf,
        )

        return leaf in self.SECRET_PROPERTIES

    def _safe_observed_value(
            self,
            value: Any,
            terraform_location: str,
    ) -> Any:

        if self._is_secret_property(
                terraform_location
        ):
            return "[REDACTED]"

        if isinstance(
                value,
                dict,
        ):

            return {
                str(k): self._safe_observed_value(
                    v,
                    f"{terraform_location}.{k}",
                )
                for k, v in value.items()
            }

        if isinstance(
                value,
                list,
        ):

            return [
                self._safe_observed_value(
                    v,
                    f"{terraform_location}[{i}]",
                )
                for i, v in enumerate(value)
            ]

        return value

    def _safe_configuration_snapshot(
            self,
            value: Any,
            current_path: str,
    ) -> Any:

        return self._safe_observed_value(
            value,
            current_path,
        )

    def _is_concrete_property_candidate(
            self,
            candidate: Dict[str, Any],
    ) -> bool:

        path = self._clean_string(
            candidate.get(
                "terraform_path"
            )
        )

        prop = self._clean_string(
            candidate.get(
                "property"
            )
        )

        if not path or not prop:
            return False

        return True

    def _is_non_validatable_property(
            self,
            candidate: Dict[str, Any],
    ) -> bool:

        prop = self._clean_string(
            candidate.get(
                "property"
            )
        ).lower()

        path = self._clean_string(
            candidate.get(
                "terraform_path"
            )
        ).lower()

        leaf = (
            path.split(".")[-1]
            if path
            else prop
        )

        leaf = re.sub(
            r"\[\d+\]",
            "",
            leaf,
        )

        return (
                prop in self.NON_VALIDATABLE_PROPERTY_NAMES
                or
                leaf in self.NON_VALIDATABLE_PROPERTY_NAMES
        )

    def _normalize_text(
            self,
            text: str,
    ) -> str:

        text = str(
            text or ""
        )

        text = (
            text
            .replace("\u201c", '"')
            .replace("\u201d", '"')
            .replace("\u2018", "'")
            .replace("\u2019", "'")
            .replace("\u00a0", " ")
            .replace("\r\n", "\n")
            .replace("\r", "\n")
        )

        text = re.sub(
            r"(\w)-\s*\n\s*(\w)",
            r"\1\2",
            text,
        )

        text = re.sub(
            r"\s+",
            " ",
            text.replace(
                "\n",
                " ",
            ).replace(
                "\t",
                " ",
            ),
        )

        return text.strip().lower()

    def _parse_single_json_object(
            self,
            response: Any,
    ) -> Dict[str, Any]:

        if response is None:
            return {}

        if hasattr(
                response,
                "content",
        ):
            response = response.content

        if isinstance(
                response,
                dict,
        ):
            return response

        text = str(
            response
        ).strip()

        if text.startswith(
                "```"
        ):

            lines = text.splitlines()

            if lines:
                lines = lines[1:]

            if (
                    lines
                    and lines[-1].strip()
                    == "```"
            ):
                lines = lines[:-1]

            text = "\n".join(
                lines
            ).strip()

        if not text:
            return {}

        try:

            parsed = json.loads(
                text
            )

            return (
                parsed
                if isinstance(
                    parsed,
                    dict,
                )
                else {}
            )

        except json.JSONDecodeError:
            pass

        start = text.find(
            "{"
        )

        if start < 0:
            return {}

        try:

            parsed, _ = (
                json.JSONDecoder().raw_decode(
                    text[start:]
                )
            )

            return (
                parsed
                if isinstance(
                    parsed,
                    dict,
                )
                else {}
            )

        except json.JSONDecodeError:

            logger.warning(
                "Unable to parse LLM JSON."
            )

            return {}

    def _deduplicate_findings(
            self,
            findings: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:

        unique: Dict[
            Tuple[Any, Any],
            Dict[str, Any],
        ] = {}

        for finding in findings:

            key = (
                finding.get(
                    "terraform_path"
                ),
                finding.get(
                    "rule",
                    finding.get(
                        "requirement"
                    ),
                ),
            )

            if key not in unique:
                unique[key] = finding
                continue

            old = unique[key]

            old_score = self._safe_numeric(
                old.get(
                    "evidence_score",
                    0,
                ),
                0,
            )

            new_score = self._safe_numeric(
                finding.get(
                    "evidence_score",
                    0,
                ),
                0,
            )

            if new_score > old_score:
                unique[key] = finding

        return list(
            unique.values()
        )

    def _clean_string(
            self,
            value: Any,
    ) -> str:

        if value is None:
            return ""

        return " ".join(
            str(value)
            .replace("\n", " ")
            .replace("\r", " ")
            .split()
        ).strip()

    def _safe_numeric(
            self,
            value: Any,
            default: float = 0.0,
    ) -> float:

        try:
            return float(value)

        except (
                TypeError,
                ValueError,
        ):
            return default

    def _strict_severity(
            self,
            severity: Any,
    ) -> Optional[str]:

        value = self._clean_string(
            severity
        ).lower()

        if value not in self.VALID_SEVERITIES:
            return None

        return {
            "critical": "Critical",
            "high": "High",
            "medium": "Medium",
            "low": "Low",
        }[value]

    # ==============================================================
    # SCORE
    # ==============================================================

    def _calculate_infrastructure_score(
            self,
            findings: List[Dict[str, Any]],
    ) -> int:

        penalty = 0

        for finding in findings:

            severity = self._strict_severity(
                finding.get(
                    "severity"
                )
            )

            if severity is None:
                continue

            penalty += self.SEVERITY_PENALTIES.get(
                severity,
                0,
            )

        return max(
            0,
            min(
                100,
                100 - penalty,
                ),
        )

    # ==============================================================
    # RESULT
    # ==============================================================

    def _build_result(
            self,
            findings: List[Dict[str, Any]],
            score_override: Optional[int] = None,
            validation_performed: bool = True,
            analysis_conclusive: bool = True,
            context_found: bool = True,
            error: Optional[str] = None,
            summary: Optional[str] = None,
            coverage: float = 0.0,
            property_coverage: float = 0.0,
            configuration_coverage: float = 0.0,
            evaluated_count: int = 0,
            total_controls: int = 0,
            unsupported_count: int = 0,
            unknown_count: int = 0,
            retrieved_property_count: int = 0,
            conclusive_property_count: int = 0,
            configuration_count: int = 0,
            conclusive_configuration_count: int = 0,
    ) -> Dict[str, Any]:

        score = (
            int(score_override)
            if score_override is not None
            else self._calculate_infrastructure_score(
                findings
            )
        )

        score = max(
            0,
            min(
                100,
                score,
            ),
        )

        # ----------------------------------------------------------
        # STATUS
        # ----------------------------------------------------------

        if (
                not validation_performed
                or not analysis_conclusive
        ):
            status = "Validation Error"

        elif findings:
            status = "Non-Compliant"

        else:
            status = "Compliant"

        # ----------------------------------------------------------
        # COUNTS
        # ----------------------------------------------------------

        critical = sum(
            1
            for finding in findings
            if self._strict_severity(
                finding.get(
                    "severity"
                )
            ) == "Critical"
        )

        high = sum(
            1
            for finding in findings
            if self._strict_severity(
                finding.get(
                    "severity"
                )
            ) == "High"
        )

        medium = sum(
            1
            for finding in findings
            if self._strict_severity(
                finding.get(
                    "severity"
                )
            ) == "Medium"
        )

        low = sum(
            1
            for finding in findings
            if self._strict_severity(
                finding.get(
                    "severity"
                )
            ) == "Low"
        )

        recommendations = [
            {
                "resource": finding.get(
                    "resource",
                    "",
                ),
                "resource_name": finding.get(
                    "resource_name",
                    "",
                ),
                "terraform_location": finding.get(
                    "terraform_path",
                    "",
                ),
                "recommendation": finding.get(
                    "recommendation",
                    "",
                ),
            }
            for finding in findings
        ]

        if summary is None:

            if findings:

                summary = (
                    "Infrastructure validation completed "
                    f"with {len(findings)} supported finding(s). "
                    f"Critical: {critical}, "
                    f"High: {high}, "
                    f"Medium: {medium}, "
                    f"Low: {low}. "
                    f"Score: {score}/100. "
                    f"Coverage: {coverage:.0%}."
                )

            elif analysis_conclusive:

                summary = (
                    "Infrastructure validation completed "
                    "without evidence-grounded violations. "
                    f"Evaluated controls: "
                    f"{evaluated_count}/{total_controls}. "
                    f"Coverage: {coverage:.0%}."
                )

            else:

                summary = (
                    "Infrastructure validation is inconclusive "
                    "because available Azure evidence was "
                    "insufficient. "
                    f"Evaluated: {evaluated_count}/{total_controls}. "
                    f"Unsupported: {unsupported_count}. "
                    f"Unknown: {unknown_count}."
                )

        return {
            "findings": findings,
            "recommendations": recommendations,
            "validation_summary": summary,
            "score": score,
            "status": status,
            "validation_performed": bool(
                validation_performed
            ),
            "analysis_conclusive": bool(
                analysis_conclusive
            ),
            "context_found": bool(
                context_found
            ),
            "error": (
                str(error)
                if error
                else None
            ),
            "coverage": round(
                float(coverage),
                4,
            ),
            "property_coverage": round(
                float(property_coverage),
                4,
            ),
            "configuration_coverage": round(
                float(configuration_coverage),
                4,
            ),
            "evaluated_count": int(
                evaluated_count
            ),
            "total_controls": int(
                total_controls
            ),
            "unsupported_count": int(
                unsupported_count
            ),
            "unknown_count": int(
                unknown_count
            ),
            "retrieved_property_count": int(
                retrieved_property_count
            ),
            "conclusive_property_count": int(
                conclusive_property_count
            ),
            "configuration_count": int(
                configuration_count
            ),
            "conclusive_configuration_count": int(
                conclusive_configuration_count
            ),
            "critical": critical,
            "high": high,
            "medium": medium,
            "low": low,
            "total_findings": len(
                findings
            ),
        }


# ================================================================
# SINGLETON
# ================================================================

validator_service = ValidatorService(
    llm_service_instance=llm_service
)