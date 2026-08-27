import json
import logging
import os
import re
from typing import Any, Dict, List, Tuple

from app.graph.state import AgentState
from app.services.retriever_service import retriever


logger = logging.getLogger(__name__)

logger.warning("========== ACTIVE RETRIEVER NODE ==========")
logger.warning("%s", os.path.abspath(__file__))


# ======================================================================
# STRUCTURAL PROPERTIES
# ======================================================================

STRUCTURAL_PROPERTY_NAMES = {
    "name",
    "resource_group_name",
    "location",
    "tags",
    "description",
    "id",
    "terraform_path_id",
}


# ======================================================================
# SECRET PROPERTIES
# ======================================================================

SECRET_PROPERTY_NAMES = {
    "password",
    "admin_password",
    "administrator_password",
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


# ======================================================================
# GENERIC SECURITY VOCABULARY
# ======================================================================

# IMPORTANT:
# This is only a retrieval vocabulary.
# It does NOT define Azure compliance rules.
SECURITY_RELEVANCE_TOKENS = (
    "security",
    "access",
    "allow",
    "deny",
    "authentication",
    "authorization",
    "identity",
    "credential",
    "password",
    "secret",
    "token",
    "key",
    "private",
    "public",
    "network",
    "subnet",
    "firewall",
    "rule",
    "source",
    "destination",
    "address",
    "port",
    "protocol",
    "ip",
    "exposure",
    "endpoint",
    "tls",
    "ssl",
    "https",
    "http",
    "encryption",
    "encrypt",
    "logging",
    "diagnostic",
    "monitor",
    "audit",
    "backup",
    "admin",
    "ssh",
    "rdp",
    "traffic",
    "interface",
)


# ======================================================================
# BASIC HELPERS
# ======================================================================

def _clean_string(value: Any) -> str:
    if value is None:
        return ""

    value = str(value).strip()

    while (
            len(value) >= 2
            and value.startswith('"')
            and value.endswith('"')
    ):
        value = value[1:-1].strip()

    return value


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        value = value.strip()

        while (
                len(value) >= 2
                and value.startswith('"')
                and value.endswith('"')
        ):
            value = value[1:-1].strip()

        return value

    if isinstance(value, list):
        return [
            _normalize_value(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            str(key): _normalize_value(item)
            for key, item in value.items()
        }

    return value


def _snake_to_words(value: str) -> str:
    """
    Generic transformation:
        min_tls_version
        -> min tls version

    No Azure-specific mapping.
    """
    if not isinstance(value, str):
        return ""

    value = re.sub(
        r"\[\d+\]",
        "",
        value,
    )

    value = value.replace(
        "_",
        " ",
    )

    value = re.sub(
        r"\s+",
        " ",
        value,
    )

    return value.strip()


def _property_leaf_name(terraform_path: str) -> str:
    if not isinstance(terraform_path, str):
        return ""

    path = terraform_path.split(".")[-1]

    path = re.sub(
        r"\[\d+\]$",
        "",
        path,
    )

    return path.strip().lower()


def _property_name(terraform_path: str) -> str:
    if not isinstance(terraform_path, str):
        return ""

    parts = terraform_path.split(
        ".",
        2,
    )

    if len(parts) < 3:
        return ""

    return parts[2]


def _resource_identity(
        terraform_path: str,
) -> Tuple[str, str]:

    if not isinstance(terraform_path, str):
        return "", ""

    parts = terraform_path.split(".")

    if len(parts) < 2:
        return "", ""

    return (
        parts[0].strip(),
        parts[1].strip(),
    )


def _resource_type_words(
        resource_type: str,
) -> str:

    if not isinstance(resource_type, str):
        return ""

    value = resource_type.strip().lower()

    if value.startswith("azurerm_"):
        value = value[len("azurerm_"):]

    return (
        value
        .replace("_", " ")
        .strip()
    )


def _is_structural_property(
        terraform_path: str,
) -> bool:

    leaf = _property_leaf_name(
        terraform_path
    )

    if not leaf:
        return True

    return leaf in STRUCTURAL_PROPERTY_NAMES


def _is_secret_path(
        terraform_path: str,
) -> bool:

    leaf = _property_leaf_name(
        terraform_path
    )

    return leaf in SECRET_PROPERTY_NAMES


def _safe_value(
        value: Any,
        terraform_path: str,
) -> Any:

    if _is_secret_path(
            terraform_path
    ):
        return "[REDACTED]"

    return _normalize_value(
        value
    )


# ======================================================================
# PROPERTY RELEVANCE
# ======================================================================

def is_security_relevant_property(
        terraform_path: str,
        value: Any,
) -> bool:

    if not isinstance(
            terraform_path,
            str,
    ):
        return False

    terraform_path = terraform_path.strip()

    if not terraform_path:
        return False

    if _is_structural_property(
            terraform_path
    ):
        return False

    leaf = _property_leaf_name(
        terraform_path
    )

    full_path = terraform_path.lower()

    # --------------------------------------------------------------
    # Access-control blocks
    # --------------------------------------------------------------

    if "security_rule" in full_path:
        return True

    # --------------------------------------------------------------
    # Network interface public/subnet settings
    # --------------------------------------------------------------

    if "ip_configuration" in full_path:
        return True

    # --------------------------------------------------------------
    # Leaf-based semantic relevance
    #
    # IMPORTANT:
    # We do NOT use the whole path here for generic matching.
    # This avoids:
    #
    # network_interface_ids
    #
    # being considered security-relevant just because it contains
    # the word "network".
    # --------------------------------------------------------------

    leaf_words = _snake_to_words(
        leaf
    ).lower()

    if any(
            token in leaf_words
            for token in SECURITY_RELEVANCE_TOKENS
    ):
        return True

    # Boolean configuration controls are useful retrieval targets.
    if isinstance(
            value,
            bool,
    ):
        return True

    return False


# ======================================================================
# PATH VALUE LOOKUP
# ======================================================================

def _split_path(
        path: str,
) -> List[str]:

    if not path:
        return []

    return [
        token.strip()
        for token in path.split(".")
        if token.strip()
    ]


def _get_value_at_path(
        configuration: Dict[str, Any],
        terraform_path: str,
        base_path: str,
) -> Tuple[bool, Any]:

    if not isinstance(
            configuration,
            dict,
    ):
        return False, None

    if not terraform_path.startswith(
            base_path
    ):
        return False, None

    remaining = terraform_path[
        len(base_path):
    ].lstrip(".")

    if not remaining:
        return False, None

    tokens = _split_path(
        remaining
    )

    current: Any = configuration

    for token in tokens:

        list_match = re.fullmatch(
            r"(.+)\[(\d+)\]",
            token,
        )

        if list_match:

            field_name = list_match.group(
                1
            )

            index = int(
                list_match.group(
                    2
                )
            )

            if not isinstance(
                    current,
                    dict,
            ):
                return False, None

            if field_name not in current:
                return False, None

            current = current[
                field_name
            ]

            if not isinstance(
                    current,
                    list,
            ):
                return False, None

            if not (
                    0 <= index < len(current)
            ):
                return False, None

            current = current[
                index
            ]

        else:

            if not isinstance(
                    current,
                    dict,
            ):
                return False, None

            if token not in current:
                return False, None

            current = current[
                token
            ]

    return True, current


# ======================================================================
# LEAF PATH COLLECTION
# ======================================================================

def _collect_leaf_paths(
        value: Any,
        current_path: str,
        output: List[str],
) -> None:

    if isinstance(
            value,
            dict,
    ):

        for key, child in value.items():

            key = str(
                key
            ).strip()

            if (
                    not key
                    or key.startswith("__")
            ):
                continue

            path = (
                f"{current_path}.{key}"
            )

            if isinstance(
                    child,
                    (
                            dict,
                            list,
                    ),
            ):

                _collect_leaf_paths(
                    value=child,
                    current_path=path,
                    output=output,
                )

            else:

                output.append(
                    path
                )

        return

    if isinstance(
            value,
            list,
    ):

        for index, child in enumerate(
                value
        ):

            indexed_path = (
                f"{current_path}[{index}]"
            )

            if isinstance(
                    child,
                    (
                            dict,
                            list,
                    ),
            ):

                _collect_leaf_paths(
                    value=child,
                    current_path=indexed_path,
                    output=output,
                )

            else:

                output.append(
                    indexed_path
                )


# ======================================================================
# CONFIGURATION BLOCK COLLECTION
# ======================================================================

def _collect_configuration_units(
        value: Any,
        current_path: str,
        resource_type: str,
        resource_name: str,
        output: List[Dict[str, Any]],
) -> None:

    if isinstance(
            value,
            dict,
    ):

        scalar_properties: Dict[
            str,
            Any
        ] = {}

        for key, child in value.items():

            key = str(
                key
            ).strip()

            if (
                    not key
                    or key.startswith("__")
            ):
                continue

            child_path = (
                f"{current_path}.{key}"
            )

            if isinstance(
                    child,
                    dict,
            ):

                _collect_configuration_units(
                    value=child,
                    current_path=child_path,
                    resource_type=resource_type,
                    resource_name=resource_name,
                    output=output,
                )

            elif isinstance(
                    child,
                    list,
            ):

                for index, item in enumerate(
                        child
                ):

                    item_path = (
                        f"{child_path}[{index}]"
                    )

                    if isinstance(
                            item,
                            (
                                    dict,
                                    list,
                            ),
                    ):

                        _collect_configuration_units(
                            value=item,
                            current_path=item_path,
                            resource_type=resource_type,
                            resource_name=resource_name,
                            output=output,
                        )

                    else:

                        scalar_properties[
                            f"{key}[{index}]"
                        ] = item

            else:

                scalar_properties[
                    key
                ] = child

        # ----------------------------------------------------------
        # Only indexed nested blocks with >=2 fields are candidates.
        #
        # But additionally require that the block contains at least
        # two security/configuration-relevant fields.
        #
        # This prevents useless units like:
        #
        # os_disk
        # source_image_reference
        #
        # ----------------------------------------------------------

        if (
                "["
                in current_path
                and
                len(scalar_properties)
                >= 2
        ):

            relevant_properties = {}

            for key, raw_value in (
                    scalar_properties.items()
            ):

                property_path = (
                    f"{current_path}.{key}"
                )

                if is_security_relevant_property(
                        terraform_path=property_path,
                        value=raw_value,
                ):

                    relevant_properties[
                        key
                    ] = _safe_value(
                        value=raw_value,
                        terraform_path=property_path,
                    )

            if len(
                    relevant_properties
            ) >= 2:

                output.append(
                    {
                        "unit_id": current_path,
                        "configuration_path": current_path,
                        "resource_type": resource_type,
                        "resource_name": resource_name,
                        "properties": {
                            key: _normalize_value(
                                value
                            )
                            for key, value
                            in scalar_properties.items()
                        },
                        "security_properties": relevant_properties,
                    }
                )

        return

    if isinstance(
            value,
            list,
    ):

        for index, item in enumerate(
                value
        ):

            item_path = (
                f"{current_path}[{index}]"
            )

            if isinstance(
                    item,
                    (
                            dict,
                            list,
                    ),
            ):

                _collect_configuration_units(
                    value=item,
                    current_path=item_path,
                    resource_type=resource_type,
                    resource_name=resource_name,
                    output=output,
                )


def extract_terraform_configuration_units(
        infrastructure: Dict[str, Any],
) -> List[Dict[str, Any]]:

    results: List[
        Dict[str, Any]
    ] = []

    resources = infrastructure.get(
        "resources",
        [],
    )

    if not isinstance(
            resources,
            list,
    ):
        return results

    for resource in resources:

        if not isinstance(
                resource,
                dict,
        ):
            continue

        resource_type = _clean_string(
            resource.get("type")
        )

        resource_name = _clean_string(
            resource.get("name")
        )

        configuration = resource.get(
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

        base_path = (
            f"{resource_type}."
            f"{resource_name}"
        )

        _collect_configuration_units(
            value=configuration,
            current_path=base_path,
            resource_type=resource_type,
            resource_name=resource_name,
            output=results,
        )

    unique = {}

    for item in results:

        unit_id = item.get(
            "unit_id",
            "",
        )

        if unit_id:
            unique[
                unit_id
            ] = item

    return list(
        unique.values()
    )


# ======================================================================
# PROPERTY EXTRACTION
# ======================================================================

def extract_terraform_properties(
        infrastructure: Dict[str, Any],
) -> List[Dict[str, Any]]:

    results: List[
        Dict[str, Any]
    ] = []

    resources = infrastructure.get(
        "resources",
        [],
    )

    if not isinstance(
            resources,
            list,
    ):
        return results

    for resource in resources:

        if not isinstance(
                resource,
                dict,
        ):
            continue

        resource_type = _clean_string(
            resource.get("type")
        )

        resource_name = _clean_string(
            resource.get("name")
        )

        configuration = resource.get(
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

        base_path = (
            f"{resource_type}."
            f"{resource_name}"
        )

        leaf_paths: List[str] = []

        _collect_leaf_paths(
            value=configuration,
            current_path=base_path,
            output=leaf_paths,
        )

        for path in leaf_paths:

            exists, value = _get_value_at_path(
                configuration=configuration,
                terraform_path=path,
                base_path=base_path,
            )

            if not exists:
                continue

            if not is_security_relevant_property(
                    terraform_path=path,
                    value=value,
            ):
                continue

            results.append(
                {
                    "terraform_path": path,
                    "resource_type": resource_type,
                    "resource_name": resource_name,
                    "terraform_property": _property_name(
                        path
                    ),
                    "observed_value": _safe_value(
                        value=value,
                        terraform_path=path,
                    ),
                    "is_secret": _is_secret_path(
                        path
                    ),
                }
            )

    unique = {}

    for item in results:

        path = item.get(
            "terraform_path",
            "",
        )

        if path:
            unique[
                path
            ] = item

    return list(
        unique.values()
    )


# ======================================================================
# PROPERTY QUERY VARIANTS
# ======================================================================

def _build_property_query_variants(
        property_entry: Dict[str, Any],
) -> List[str]:

    resource_type = str(
        property_entry.get(
            "resource_type",
            "",
        )
    ).strip()

    resource_name = str(
        property_entry.get(
            "resource_name",
            "",
        )
    ).strip()

    terraform_property = str(
        property_entry.get(
            "terraform_property",
            "",
        )
    ).strip()

    terraform_path = str(
        property_entry.get(
            "terraform_path",
            "",
        )
    ).strip()

    observed_value = _normalize_value(
        property_entry.get(
            "observed_value"
        )
    )

    resource_words = _resource_type_words(
        resource_type
    )

    property_words = _snake_to_words(
        terraform_property
    )

    value_text = json.dumps(
        observed_value,
        ensure_ascii=False,
        default=str,
    )

    # Query 1: precise Terraform/Azure relation
    q1 = (
        f"Azure {resource_words} documentation. "
        f"Configuration concept: {property_words}. "
        f"Observed configuration value: {value_text}. "
        f"Terraform resource type: {resource_type}. "
        "Find explicit Azure requirements, restrictions, "
        "security guidance, or expected configuration "
        "for this same resource and same configuration concept."
    )

    # Query 2: semantic concept
    q2 = (
        f"Azure {resource_words}. "
        f"{property_words}. "
        f"{value_text}. "
        "Find explicit security or configuration guidance "
        "directly applicable to this Azure resource."
    )

    # Query 3: path-aware
    q3 = (
        f"Azure {resource_words} configuration. "
        f"Terraform property {terraform_property}. "
        f"Configuration path {terraform_path}. "
        f"Observed value {value_text}. "
        "Find direct documentation for this configuration."
    )

    return [
        q1,
        q2,
        q3,
    ]


def build_property_queries(
        infrastructure: Dict[str, Any],
) -> List[Dict[str, Any]]:

    logger.warning(
        "========== PROPERTY QUERY BUILDER =========="
    )

    properties = extract_terraform_properties(
        infrastructure
    )

    queries: List[
        Dict[str, Any]
    ] = []

    for property_entry in properties:

        variants = _build_property_query_variants(
            property_entry
        )

        queries.append(
            {
                "query_type": "terraform_property",
                "queries": variants,
                "query": variants[0],
                "terraform_path": property_entry[
                    "terraform_path"
                ],
                "terraform_property": property_entry[
                    "terraform_property"
                ],
                "resource_type": property_entry[
                    "resource_type"
                ],
                "resource_name": property_entry[
                    "resource_name"
                ],
                "observed_value": property_entry[
                    "observed_value"
                ],
                "is_secret": property_entry[
                    "is_secret"
                ],
            }
        )

    logger.info(
        "Generated property query groups=%d",
        len(queries),
    )

    return queries


# ======================================================================
# CONFIGURATION QUERY VARIANTS
# ======================================================================

def _build_configuration_query_variants(
        unit: Dict[str, Any],
) -> List[str]:

    resource_type = str(
        unit.get(
            "resource_type",
            "",
        )
    ).strip()

    configuration_path = str(
        unit.get(
            "configuration_path",
            "",
        )
    ).strip()

    properties = unit.get(
        "properties",
        {},
    )

    security_properties = unit.get(
        "security_properties",
        {},
    )

    resource_words = _resource_type_words(
        resource_type
    )

    properties_json = json.dumps(
        properties,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    security_json = json.dumps(
        security_properties,
        ensure_ascii=False,
        indent=2,
        default=str,
    )

    property_words = " ".join(
        _snake_to_words(
            key
        )
        for key in security_properties.keys()
    )

    # Query 1
    q1 = (
        f"Azure {resource_words} security configuration. "
        f"Configuration block: {configuration_path}. "
        f"Security configuration fields: {property_words}. "
        f"Observed values: {security_json}. "
        "Find explicit Azure requirements or restrictions "
        "that apply to this complete configuration."
    )

    # Query 2
    q2 = (
        f"Azure {resource_words}. "
        f"{property_words}. "
        f"Configuration values: {security_json}. "
        "Find directly applicable Azure security guidance "
        "for the same configuration concept."
    )

    # Query 3
    q3 = (
        f"Azure {resource_words} configuration. "
        f"Observed block: {properties_json}. "
        "Find explicit documentation for this configuration "
        "and not generic architecture advice."
    )

    return [
        q1,
        q2,
        q3,
    ]


def build_configuration_queries(
        infrastructure: Dict[str, Any],
) -> List[Dict[str, Any]]:

    logger.warning(
        "========== CONFIGURATION QUERY BUILDER =========="
    )

    units = extract_terraform_configuration_units(
        infrastructure
    )

    queries: List[
        Dict[str, Any]
    ] = []

    for unit in units:

        configuration_path = str(
            unit.get(
                "configuration_path",
                "",
            )
        ).strip()

        if not configuration_path:
            continue

        variants = (
            _build_configuration_query_variants(
                unit
            )
        )

        queries.append(
            {
                "query_type": "terraform_configuration",
                "queries": variants,
                "query": variants[0],
                "configuration_path": configuration_path,
                "terraform_path": configuration_path,
                "resource_type": unit.get(
                    "resource_type",
                    "",
                ),
                "resource_name": unit.get(
                    "resource_name",
                    "",
                ),
                "properties": unit.get(
                    "properties",
                    {},
                ),
                "security_properties": unit.get(
                    "security_properties",
                    {},
                ),
            }
        )

    logger.info(
        "Generated configuration query groups=%d",
        len(queries),
    )

    return queries


# ======================================================================
# DOCUMENT ENRICHMENT
# ======================================================================

def _enrich_property_document(
        document: Dict[str, Any],
        query_item: Dict[str, Any],
        query_text: str,
) -> Dict[str, Any]:

    enriched = dict(
        document
    )

    terraform_path = query_item.get(
        "terraform_path",
        "",
    )

    enriched[
        "_retrieval_query"
    ] = query_text

    enriched[
        "_retrieval_query_type"
    ] = "terraform_property"

    enriched[
        "_terraform_path"
    ] = terraform_path

    enriched[
        "_terraform_property"
    ] = query_item.get(
        "terraform_property",
        "",
    )

    enriched[
        "_resource_type"
    ] = query_item.get(
        "resource_type",
        "",
    )

    enriched[
        "_resource_name"
    ] = query_item.get(
        "resource_name",
        "",
    )

    enriched[
        "_observed_value"
    ] = query_item.get(
        "observed_value"
    )

    enriched[
        "query_type"
    ] = "terraform_property"

    enriched[
        "terraform_path"
    ] = terraform_path

    enriched[
        "terraform_path_id"
    ] = terraform_path

    enriched[
        "terraform_property"
    ] = query_item.get(
        "terraform_property",
        "",
    )

    enriched[
        "resource_type"
    ] = query_item.get(
        "resource_type",
        "",
    )

    enriched[
        "resource_name"
    ] = query_item.get(
        "resource_name",
        "",
    )

    enriched[
        "observed_value"
    ] = query_item.get(
        "observed_value"
    )

    return enriched


def _enrich_configuration_document(
        document: Dict[str, Any],
        query_item: Dict[str, Any],
        query_text: str,
) -> Dict[str, Any]:

    enriched = dict(
        document
    )

    configuration_path = query_item.get(
        "configuration_path",
        "",
    )

    enriched[
        "_retrieval_query"
    ] = query_text

    enriched[
        "_retrieval_query_type"
    ] = "terraform_configuration"

    enriched[
        "_configuration_path"
    ] = configuration_path

    enriched[
        "_terraform_path"
    ] = configuration_path

    enriched[
        "_terraform_property"
    ] = ""

    enriched[
        "_resource_type"
    ] = query_item.get(
        "resource_type",
        "",
    )

    enriched[
        "_resource_name"
    ] = query_item.get(
        "resource_name",
        "",
    )

    enriched[
        "_configuration_properties"
    ] = query_item.get(
        "properties",
        {},
    )

    enriched[
        "_security_properties"
    ] = query_item.get(
        "security_properties",
        {},
    )

    enriched[
        "query_type"
    ] = "terraform_configuration"

    enriched[
        "configuration_path"
    ] = configuration_path

    enriched[
        "terraform_path"
    ] = configuration_path

    enriched[
        "terraform_path_id"
    ] = configuration_path

    enriched[
        "terraform_property"
    ] = ""

    enriched[
        "resource_type"
    ] = query_item.get(
        "resource_type",
        "",
    )

    enriched[
        "resource_name"
    ] = query_item.get(
        "resource_name",
        "",
    )

    enriched[
        "configuration_properties"
    ] = query_item.get(
        "properties",
        {},
    )

    enriched[
        "security_properties"
    ] = query_item.get(
        "security_properties",
        {},
    )

    return enriched


# ======================================================================
# DEDUPLICATION
# ======================================================================

def _deduplicate_documents(
        documents: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    unique_documents = []
    seen = set()

    for document in documents:

        if not isinstance(
                document,
                dict,
        ):
            continue

        source = str(
            document.get(
                "source",
                "",
            )
        )

        page = str(
            document.get(
                "page",
                "",
            )
        )

        content = str(
            document.get(
                "content",
                "",
            )
        )

        query_type = str(
            document.get(
                "query_type",
                "",
            )
        )

        terraform_path = str(
            document.get(
                "_terraform_path",
                "",
            )
        )

        configuration_path = str(
            document.get(
                "_configuration_path",
                "",
            )
        )

        key = (
            source,
            page,
            content[:500],
            query_type,
            terraform_path,
            configuration_path,
        )

        if key in seen:
            continue

        seen.add(key)

        unique_documents.append(
            document
        )

    return unique_documents


# ======================================================================
# NORMAL RAG
# ======================================================================

async def _normal_retrieval(
        state: AgentState,
) -> Dict[str, Any]:

    query = state.get(
        "current_query"
    )

    if (
            not isinstance(
                query,
                str,
            )
            or
            not query.strip()
    ):
        query = state.get(
            "prompt",
            "",
        )

    if (
            not isinstance(
                query,
                str,
            )
            or
            not query.strip()
    ):
        return {
            "retrieved_documents": [],
            "context_found": False,
            "status": "retrieval_empty",
        }

    try:

        documents = await retriever.retrieve(
            query=query.strip(),
            limit=10,
        )

    except Exception as exc:

        logger.exception(
            "Normal retrieval failed: %s",
            exc,
        )

        return {
            "retrieved_documents": [],
            "context_found": False,
            "status": "retrieval_failed",
        }

    valid_documents = [
        document
        for document in documents
        if (
                isinstance(
                    document,
                    dict,
                )
                and
                str(
                    document.get(
                        "content",
                        "",
                    )
                ).strip()
        )
    ]

    return {
        "retrieved_documents": valid_documents,
        "context_found": bool(
            valid_documents
        ),
        "status": (
            "retrieved"
            if valid_documents
            else "retrieval_empty"
        ),
    }


# ======================================================================
# IaC RETRIEVAL
# ======================================================================

async def _iac_retrieval(
        infrastructure: Dict[str, Any],
) -> Dict[str, Any]:

    configuration_queries = (
        build_configuration_queries(
            infrastructure
        )
    )

    property_queries = (
        build_property_queries(
            infrastructure
        )
    )

    if (
            not configuration_queries
            and
            not property_queries
    ):

        logger.warning(
            "No Terraform validation queries generated."
        )

        return {
            "retrieved_documents": [],
            "context_found": False,
            "status": "retrieval_empty",
        }

    all_documents: List[
        Dict[str, Any]
    ] = []

    # ==============================================================
    # CONFIGURATION RETRIEVAL
    # ==============================================================

    logger.warning(
        "========== CONFIGURATION RETRIEVAL =========="
    )

    for query_index, query_item in enumerate(
            configuration_queries,
            start=1,
    ):

        variants = query_item.get(
            "queries",
            [],
        )

        if not variants:
            variants = [
                query_item.get(
                    "query",
                    "",
                )
            ]

        for variant_index, query in enumerate(
                variants,
                start=1,
        ):

            query = str(
                query
                or ""
            ).strip()

            if not query:
                continue

            logger.info(
                (
                    "CONFIGURATION RETRIEVAL "
                    "%d.%d/%d"
                ),
                query_index,
                variant_index,
                len(variants),
            )

            logger.info(
                "Path=%s",
                query_item.get(
                    "configuration_path",
                    "",
                ),
            )

            try:

                documents = await retriever.retrieve(
                    query=query,
                    limit=5,
                )

            except Exception as exc:

                logger.exception(
                    (
                        "Configuration retrieval failed | "
                        "path=%s | error=%s"
                    ),
                    query_item.get(
                        "configuration_path",
                        "",
                    ),
                    exc,
                )

                continue

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

                all_documents.append(
                    _enrich_configuration_document(
                        document=document,
                        query_item=query_item,
                        query_text=query,
                    )
                )

    # ==============================================================
    # PROPERTY RETRIEVAL
    # ==============================================================

    logger.warning(
        "========== PROPERTY RETRIEVAL =========="
    )

    for query_index, query_item in enumerate(
            property_queries,
            start=1,
    ):

        variants = query_item.get(
            "queries",
            [],
        )

        if not variants:
            variants = [
                query_item.get(
                    "query",
                    "",
                )
            ]

        for variant_index, query in enumerate(
                variants,
                start=1,
        ):

            query = str(
                query
                or ""
            ).strip()

            if not query:
                continue

            logger.info(
                (
                    "PROPERTY RETRIEVAL "
                    "%d.%d/%d | path=%s"
                ),
                query_index,
                variant_index,
                len(variants),
                query_item.get(
                    "terraform_path",
                    "",
                ),
            )

            try:

                documents = await retriever.retrieve(
                    query=query,
                    limit=5,
                )

            except Exception as exc:

                logger.exception(
                    (
                        "Property retrieval failed | "
                        "path=%s | error=%s"
                    ),
                    query_item.get(
                        "terraform_path",
                        "",
                    ),
                    exc,
                )

                continue

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

                all_documents.append(
                    _enrich_property_document(
                        document=document,
                        query_item=query_item,
                        query_text=query,
                    )
                )

    # ==============================================================
    # DEDUPLICATION
    # ==============================================================

    unique_documents = (
        _deduplicate_documents(
            all_documents
        )
    )

    configuration_count = sum(
        1
        for document in unique_documents
        if document.get(
            "query_type"
        )
        ==
        "terraform_configuration"
    )

    property_count = sum(
        1
        for document in unique_documents
        if document.get(
            "query_type"
        )
        ==
        "terraform_property"
    )

    logger.warning(
        "Total retrieved validation documents=%d",
        len(unique_documents),
    )

    logger.warning(
        "Configuration documents=%d",
        configuration_count,
    )

    logger.warning(
        "Property documents=%d",
        property_count,
    )

    # ==============================================================
    # LOGGING
    # ==============================================================

    for index, document in enumerate(
            unique_documents[:150],
            start=1,
    ):

        logger.warning(
            (
                "RETRIEVED #%d | "
                "query_type=%s | "
                "terraform_path=%s | "
                "configuration_path=%s | "
                "property=%s | "
                "resource=%s.%s | "
                "source=%s | "
                "page=%s"
            ),
            index,
            document.get(
                "query_type",
                "",
            ),
            document.get(
                "_terraform_path",
                "",
            ),
            document.get(
                "_configuration_path",
                "",
            ),
            document.get(
                "_terraform_property",
                "",
            ),
            document.get(
                "_resource_type",
                "",
            ),
            document.get(
                "_resource_name",
                "",
            ),
            document.get(
                "source",
                "",
            ),
            document.get(
                "page",
                "",
            ),
        )

    return {
        "retrieved_documents": unique_documents,
        "context_found": bool(
            unique_documents
        ),
        "status": (
            "retrieved"
            if unique_documents
            else "retrieval_empty"
        ),
    }


# ======================================================================
# RETRIEVER NODE
# ======================================================================

async def retriever_node(
        state: AgentState,
) -> Dict[str, Any]:

    logger.info(
        "========== RETRIEVER NODE =========="
    )

    terraform_code = state.get(
        "terraform_code",
        "",
    )

    infrastructure = state.get(
        "infrastructure",
        {},
    )

    if not isinstance(
            infrastructure,
            dict,
    ):
        infrastructure = {}

    resources = infrastructure.get(
        "resources",
        [],
    )

    if not isinstance(
            resources,
            list,
    ):
        resources = []

    is_iac = (
            isinstance(
                terraform_code,
                str,
            )
            and
            bool(
                terraform_code.strip()
            )
            and
            bool(resources)
    )

    if not is_iac:
        return await _normal_retrieval(
            state
        )

    return await _iac_retrieval(
        infrastructure
    )