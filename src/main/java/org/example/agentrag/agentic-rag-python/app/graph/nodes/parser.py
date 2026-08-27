import logging
from typing import Any, Dict, List, Tuple

import hcl2


logger = logging.getLogger(__name__)


# ============================================================
# CLEAN HCL
# ============================================================

def clean_hcl(value: Any) -> Any:
    """
    Nettoie récursivement la structure produite par python-hcl2.

    Aucune règle Azure n'est utilisée ici.
    """

    if isinstance(value, dict):

        result = {}

        for key, val in value.items():

            # Métadonnées internes éventuelles de hcl2
            if str(key).startswith("__") and str(key).endswith("__"):
                continue

            result[key] = clean_hcl(val)

        return result

    if isinstance(value, list):

        return [
            clean_hcl(item)
            for item in value
        ]

    return value


# ============================================================
# NORMALIZE STRING
# ============================================================

def normalize_string(value: Any) -> str:
    """
    Normalise une valeur textuelle.
    """

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


# ============================================================
# EXTRACT BALANCED BLOCK
# ============================================================

def _extract_balanced_block(
        text: str,
        start: int,
) -> Tuple[str, int]:
    """
    Extrait un bloc HCL équilibré à partir d'une position
    contenant '{'.

    Retourne :

        (bloc, position_fin)

    Cette fonction est générique et ne connaît aucune
    ressource Azure.
    """

    brace_start = text.find(
        "{",
        start,
    )

    if brace_start == -1:

        raise ValueError(
            f"No opening brace found after position {start}."
        )

    depth = 0
    in_string = False
    escaped = False

    for index in range(
            brace_start,
            len(text),
    ):

        char = text[index]

        # Gestion des chaînes Terraform
        if (
                char == '"'
                and not escaped
        ):
            in_string = not in_string

        if (
                char == "\\"
                and not escaped
        ):
            escaped = True

        else:
            escaped = False

        if in_string:
            continue

        if char == "{":

            depth += 1

        elif char == "}":

            depth -= 1

            if depth == 0:

                return (
                    text[start:index + 1],
                    index + 1,
                )

    raise ValueError(
        "Unbalanced Terraform braces."
    )


# ============================================================
# EXTRACT TERRAFORM BLOCKS
# ============================================================

def extract_terraform_blocks(
        value: str,
) -> str:
    """
    Extrait tous les blocs Terraform top-level.

    Exemple :

        resource "x" "a" {
            ...
        }

        resource "y" "b" {
            ...
        }

    Le texte utilisateur avant/après Terraform est ignoré.

    Aucune connaissance Azure n'est utilisée.
    """

    if not value:
        return ""

    text = value.strip()

    # ========================================================
    # CLEAN MARKDOWN FENCES
    # ========================================================

    if "```" in text:

        parts = text.split("```")

        code_blocks = []

        for index in range(
                1,
                len(parts),
                2,
        ):

            block = parts[index].strip()

            lines = block.splitlines()

            if lines:

                first_line = (
                    lines[0]
                    .strip()
                    .lower()
                )

                if first_line in {
                    "hcl",
                    "terraform",
                    "tf",
                }:

                    lines = lines[1:]

            block = "\n".join(
                lines
            ).strip()

            if block:
                code_blocks.append(block)

        if code_blocks:

            text = "\n\n".join(
                code_blocks
            )

    # ========================================================
    # TERRAFORM TOP-LEVEL CONSTRUCTIONS
    # ========================================================

    keywords = (
        "resource",
        "data",
        "variable",
        "locals",
        "module",
        "terraform",
        "provider",
        "output",
        "moved",
        "import",
        "check",
    )

    blocks = []

    position = 0

    while position < len(text):

        candidates = []

        for keyword in keywords:

            search_position = text.find(
                keyword,
                position,
            )

            if search_position != -1:

                candidates.append(
                    (
                        search_position,
                        keyword,
                    )
                )

        if not candidates:
            break

        start, keyword = min(
            candidates,
            key=lambda item: item[0],
        )

        # ====================================================
        # VERIFY TOKEN BOUNDARIES
        # ====================================================

        before_ok = (
                start == 0
                or not (
                text[start - 1].isalnum()
                or text[start - 1] == "_"
        )
        )

        after_position = (
                start + len(keyword)
        )

        after_ok = (
                after_position >= len(text)
                or not (
                text[after_position].isalnum()
                or text[after_position] == "_"
        )
        )

        if not before_ok or not after_ok:

            position = (
                    start + len(keyword)
            )

            continue

        # ====================================================
        # EXTRACT BLOCK
        # ====================================================

        try:

            block, end_position = (
                _extract_balanced_block(
                    text,
                    start,
                )
            )

            blocks.append(block)

            position = end_position

        except ValueError as exc:

            logger.warning(
                "Unable to extract Terraform block "
                "starting at position %d: %s",
                start,
                exc,
            )

            break

    result = "\n\n".join(
        blocks
    ).strip()

    return result


# ============================================================
# PARSE RESOURCES
# ============================================================

def parse_resources(
        parsed: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """
    Transforme les resources Terraform hcl2
    en structure uniforme.

    Aucune connaissance Azure n'est utilisée.
    """

    resources = []

    raw_resources = parsed.get(
        "resource",
        [],
    )

    if not isinstance(
            raw_resources,
            list,
    ):
        return resources

    for resource_group in raw_resources:

        if not isinstance(
                resource_group,
                dict,
        ):
            continue

        for raw_type, resource_definitions in (
                resource_group.items()
        ):

            resource_type = normalize_string(
                raw_type
            )

            if not isinstance(
                    resource_definitions,
                    dict,
            ):
                continue

            for raw_name, configuration in (
                    resource_definitions.items()
            ):

                resource_name = normalize_string(
                    raw_name
                )

                resources.append(
                    {
                        "type": resource_type,
                        "name": resource_name,
                        "terraform_path_id": (
                            f"{resource_type}.{resource_name}"
                        ),
                        "configuration": clean_hcl(
                            configuration
                        ),
                    }
                )

    return resources


# ============================================================
# PARSER NODE
# ============================================================

async def parser_node(
        state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Node LangGraph responsable uniquement
    du parsing Terraform.

    Il :

        1. récupère terraform_code
        2. extrait les blocs Terraform
        3. parse avec python-hcl2
        4. construit une structure uniforme

    Il ne fait aucune analyse de sécurité.
    """

    terraform_code = state.get(
        "terraform_code"
    )

    # ========================================================
    # VALIDATION
    # ========================================================

    if not terraform_code:

        return {
            "infrastructure": {
                "resources": []
            },
            "parse_status": "failed",
            "error": "No Terraform code provided.",
        }

    if not isinstance(
            terraform_code,
            str,
    ):

        return {
            "infrastructure": {
                "resources": []
            },
            "parse_status": "failed",
            "error": (
                "terraform_code must be a string."
            ),
        }

    try:

        # ====================================================
        # EXTRACT
        # ====================================================

        logger.info(
            "Extracting Terraform blocks..."
        )

        extracted_code = (
            extract_terraform_blocks(
                terraform_code
            )
        )

        if not extracted_code:

            return {
                "infrastructure": {
                    "resources": []
                },
                "parse_status": "failed",
                "error": (
                    "No Terraform blocks "
                    "could be extracted."
                ),
            }

        logger.info(
            "Terraform code extracted: %d characters.",
            len(extracted_code),
        )

        logger.debug(
            "Extracted Terraform:\n%s",
            extracted_code,
        )

        # ====================================================
        # HCL PARSING
        # ====================================================

        logger.info(
            "Parsing Terraform with python-hcl2..."
        )

        parsed = hcl2.loads(
            extracted_code
        )

        # ====================================================
        # RESOURCE CONVERSION
        # ====================================================

        resources = parse_resources(
            parsed
        )

        logger.info(
            "Terraform parsing completed. "
            "%d resources detected.",
            len(resources),
        )

        if not resources:

            return {
                "infrastructure": {
                    "resources": []
                },
                "parse_status": "failed",
                "error": (
                    "Terraform was parsed successfully "
                    "but no resources were detected."
                ),
            }

        # ====================================================
        # LOG RESOURCES
        # ====================================================

        for resource in resources:

            logger.info(
                "Detected resource: %s",
                resource.get(
                    "terraform_path_id"
                ),
            )

        # ====================================================
        # SUCCESS
        # ====================================================

        return {
            "infrastructure": {
                "resources": resources
            },
            "terraform_code": extracted_code,
            "parse_status": "success",
            "error": None,
        }

    except Exception as exc:

        logger.exception(
            "Terraform parsing failed."
        )

        return {
            "infrastructure": {
                "resources": []
            },
            "parse_status": "failed",
            "error": str(exc),
        }
