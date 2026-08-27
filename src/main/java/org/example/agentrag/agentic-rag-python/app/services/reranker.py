import logging
from collections import OrderedDict
from typing import Any, Dict, List

from sentence_transformers import CrossEncoder


logger = logging.getLogger(__name__)


class RerankerService:
    """
    CrossEncoder reranker.

    Supports:

    1. Normal RAG reranking.
    2. Property-aware IaC reranking.

    IaC property-aware reranking:
        Terraform property
            ->
        original retrieval query
            ->
        CrossEncoder
            ->
        top-k documents for THAT property

    Important:
    ----------
    We do NOT perform one global top-k over all Terraform properties.

    Otherwise:
        property A -> 8 documents
        property B -> 8 documents
        property C -> 8 documents
        ...

    could result in only a few properties surviving the global top-k.

    Instead, each Terraform property receives its own top-k quota.
    """

    def __init__(
            self,
            model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
    ):
        self.model_name = model_name

        logger.info(
            "Loading reranker model: %s",
            self.model_name,
        )

        self.model = CrossEncoder(
            self.model_name
        )

        logger.info(
            "Reranker model loaded successfully."
        )

    # ==================================================================
    # NORMAL RAG RERANKING
    # ==================================================================

    def rerank(
            self,
            query: str,
            documents: List[Dict[str, Any]],
            top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Standard global reranking for normal RAG.

        Used when there is one user question rather than multiple
        Terraform-property retrieval queries.
        """

        if not isinstance(
                query,
                str,
        ):
            return []

        query = query.strip()

        if not query:
            return []

        if not isinstance(
                documents,
                list,
        ) or not documents:
            return []

        if top_k <= 0:
            return []

        pairs = []
        valid_documents = []

        for document in documents:

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

            pairs.append(
                (
                    query,
                    content,
                )
            )

            valid_documents.append(
                document
            )

        if not pairs:
            return []

        try:

            scores = self.model.predict(
                pairs
            )

        except Exception as exc:

            logger.exception(
                "Normal CrossEncoder reranking failed: %s",
                exc,
            )

            return []

        ranked_documents = []

        for document, score in zip(
                valid_documents,
                scores,
        ):

            enriched = dict(
                document
            )

            enriched["rerank_score"] = float(
                score
            )

            ranked_documents.append(
                enriched
            )

        ranked_documents.sort(
            key=lambda item: item.get(
                "rerank_score",
                0.0,
            ),
            reverse=True,
        )

        return ranked_documents[
            :top_k
        ]

    # ==================================================================
    # PROPERTY-AWARE IaC RERANKING
    # ==================================================================

    def rerank_by_property(
            self,
            documents: List[Dict[str, Any]],
            top_k_per_property: int = 3,
            max_total: int = 40,
    ) -> List[Dict[str, Any]]:
        """
        Property-aware reranking for Terraform/IaC.

        Every retrieved document is associated with the Terraform
        property that generated its retrieval query.

        Expected metadata:

            _retrieval_query
            _terraform_path
            _terraform_property
            _resource_type
            _resource_name

        or the public equivalents:

            terraform_path
            terraform_property
            resource_type
            resource_name

        Example:

            azurerm_storage_account.storage.min_tls_version
                -> top 3 documents

            azurerm_storage_account.storage.public_network_access_enabled
                -> top 3 documents

            azurerm_linux_virtual_machine.web_vm
                .disable_password_authentication
                -> top 3 documents

        The method guarantees that the global ranking step does not
        happen before property quotas are applied.
        """

        if not isinstance(
                documents,
                list,
        ) or not documents:
            return []

        if top_k_per_property <= 0:
            return []

        if max_total <= 0:
            return []

        # ==============================================================
        # GROUP BY TERRAFORM PROPERTY
        # ==============================================================

        groups: "OrderedDict[str, List[Dict[str, Any]]]" = (
            OrderedDict()
        )

        for document in documents:

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

            terraform_path = str(
                document.get(
                    "_terraform_path",
                    document.get(
                        "terraform_path",
                        "",
                    ),
                )
                or ""
            ).strip()

            retrieval_query = str(
                document.get(
                    "_retrieval_query",
                    "",
                )
                or ""
            ).strip()

            if not terraform_path:
                logger.warning(
                    "Skipping document without terraform property path."
                )
                continue

            if not retrieval_query:
                logger.warning(
                    "Skipping document without retrieval query | path=%s",
                    terraform_path,
                )
                continue

            groups.setdefault(
                terraform_path,
                [],
            ).append(
                document
            )

        if not groups:

            logger.warning(
                "No property-scoped documents found for reranking."
            )

            return []

        logger.info(
            "Property-aware reranking groups=%d",
            len(groups),
        )

        # ==============================================================
        # RERANK EACH PROPERTY INDEPENDENTLY
        # ==============================================================

        property_results: Dict[
            str,
            List[Dict[str, Any]],
        ] = {}

        for terraform_path, group in groups.items():

            if not group:
                continue

            # ----------------------------------------------------------
            # The retrieval query is identical for documents produced
            # by the same property. Take it from the first document.
            # ----------------------------------------------------------

            query = str(
                group[0].get(
                    "_retrieval_query",
                    "",
                )
                or ""
            ).strip()

            if not query:
                continue

            pairs = []
            valid_documents = []

            for document in group:

                content = str(
                    document.get(
                        "content",
                        "",
                    )
                ).strip()

                if not content:
                    continue

                pairs.append(
                    (
                        query,
                        content,
                    )
                )

                valid_documents.append(
                    document
                )

            if not pairs:
                continue

            logger.info(
                (
                    "Reranking property | "
                    "path=%s | documents=%d"
                ),
                terraform_path,
                len(valid_documents),
            )

            try:

                scores = self.model.predict(
                    pairs
                )

            except Exception as exc:

                logger.exception(
                    (
                        "CrossEncoder property reranking failed | "
                        "path=%s | error=%s"
                    ),
                    terraform_path,
                    exc,
                )

                continue

            ranked_group: List[
                Dict[str, Any]
            ] = []

            for document, score in zip(
                    valid_documents,
                    scores,
            ):

                enriched = dict(
                    document
                )

                enriched["rerank_score"] = float(
                    score
                )

                # ------------------------------------------------------
                # Make sure property metadata survives reranking.
                # ------------------------------------------------------

                enriched["_terraform_path"] = (
                        enriched.get(
                            "_terraform_path",
                            terraform_path,
                        )
                        or terraform_path
                )

                enriched["terraform_path"] = (
                        enriched.get(
                            "terraform_path",
                            terraform_path,
                        )
                        or terraform_path
                )

                enriched["query_type"] = (
                        enriched.get(
                            "query_type",
                            "terraform_property",
                        )
                        or "terraform_property"
                )

                ranked_group.append(
                    enriched
                )

            ranked_group.sort(
                key=lambda item: item.get(
                    "rerank_score",
                    0.0,
                ),
                reverse=True,
            )

            # ----------------------------------------------------------
            # Property quota.
            # ----------------------------------------------------------

            property_results[
                terraform_path
            ] = ranked_group[
                :top_k_per_property
            ]

            logger.info(
                (
                    "Property reranked | "
                    "path=%s | selected=%d"
                ),
                terraform_path,
                len(
                    property_results[
                        terraform_path
                    ]
                ),
            )

        # ==============================================================
        # PRESERVE PROPERTY COVERAGE
        # ==============================================================

        selected: List[
            Dict[str, Any]
        ] = []

        for terraform_path, ranked_group in (
                property_results.items()
        ):

            selected.extend(
                ranked_group
            )

        if not selected:
            return []

        # ==============================================================
        # GLOBAL LIMIT
        # ==============================================================

        if len(selected) <= max_total:
            return selected

        # --------------------------------------------------------------
        # If there are more than max_total documents, do NOT simply
        # take the highest global scores because that could eliminate
        # entire Terraform properties.
        #
        # Round-robin keeps property coverage.
        # --------------------------------------------------------------

        selected_by_property = {
            path: list(group)
            for path, group in property_results.items()
            if group
        }

        balanced: List[
            Dict[str, Any]
        ] = []

        while (
                selected_by_property
                and len(balanced) < max_total
        ):

            empty_paths = []

            for terraform_path, group in (
                    selected_by_property.items()
            ):

                if not group:

                    empty_paths.append(
                        terraform_path
                    )

                    continue

                balanced.append(
                    group.pop(0)
                )

                if len(balanced) >= max_total:
                    break

            for terraform_path in empty_paths:
                selected_by_property.pop(
                    terraform_path,
                    None,
                )

        # --------------------------------------------------------------
        # Finally order the selected documents by rerank score so the
        # most relevant retained documents appear first.
        # --------------------------------------------------------------

        balanced.sort(
            key=lambda item: item.get(
                "rerank_score",
                0.0,
            ),
            reverse=True,
        )

        logger.info(
            (
                "Property-aware reranking complete | "
                "properties=%d | selected=%d"
            ),
            len(property_results),
            len(balanced),
        )

        return balanced

    # ==================================================================
    # BACKWARD COMPATIBILITY
    # ==================================================================

    def rerank_by_source_query(
            self,
            documents: List[Dict[str, Any]],
            top_k_per_property: int = 3,
            max_total: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Backward-compatible alias.

        Older code calls:

            rerank_by_source_query(...)

        New code calls:

            rerank_by_property(...)

        Both use the same property-aware algorithm.
        """

        return self.rerank_by_property(
            documents=documents,
            top_k_per_property=top_k_per_property,
            max_total=max_total,
        )


# ======================================================================
# SINGLETON
# ======================================================================

reranker_service = RerankerService()