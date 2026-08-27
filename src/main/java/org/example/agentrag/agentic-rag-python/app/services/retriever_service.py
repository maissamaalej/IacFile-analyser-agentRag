import logging
from typing import Any, Dict, List

from app.services.embedding_service import embedding_service
from app.services.qdrant import qdrant


logger = logging.getLogger(__name__)


class Retriever:
    """
    Generic Azure documentation retriever.

    Responsibilities
    ----------------
    1. Embed query.
    2. Search Qdrant.
    3. Return documents.

    This layer MUST NOT:
    - decide compliance;
    - assign severity;
    - create findings;
    - hardcode Azure security rules;
    - inspect Terraform semantics.
    """

    async def retrieve(
            self,
            query: str,
            limit: int = 10,
    ) -> List[Dict[str, Any]]:

        if not isinstance(
                query,
                str,
        ):
            return []

        query = query.strip()

        if not query:
            return []

        try:

            limit = int(limit)

        except (
                TypeError,
                ValueError,
        ):

            limit = 10

        limit = max(
            1,
            min(
                limit,
                20,
            ),
        )

        try:

            # ======================================================
            # 1. QUERY EMBEDDING
            # ======================================================

            query_vector = await (
                embedding_service.embed(
                    query
                )
            )

            if not query_vector:
                logger.warning(
                    "Empty embedding returned."
                )
                return []

            # ======================================================
            # 2. QDRANT SEARCH
            # ======================================================

            documents = await qdrant.search(
                query_vector,
                limit,
            )

            if not isinstance(
                    documents,
                    list,
            ):
                return []

            valid_documents: List[
                Dict[str, Any]
            ] = []

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

                valid_documents.append(
                    document
                )

            logger.debug(
                "Retrieved %d documents.",
                len(valid_documents),
            )

            return valid_documents

        except Exception as exc:

            logger.exception(
                "Retriever failed: %s",
                exc,
            )

            return []


retriever = Retriever()