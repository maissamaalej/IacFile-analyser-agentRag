import logging

logger = logging.getLogger(__name__)


TERRAFORM_KEYWORDS = [
    "terraform",
    "resource",
    "provider",
    "variable",
    "module",
    "azurerm_",
    "backend",
    "data"
]


async def iac_detector_node(state):

    logger.info(
        "========== IAC DETECTOR =========="
    )


    # récupérer les données
    prompt = state.get(
        "prompt"
    ) or ""


    terraform_code = state.get(
        "terraform_code"
    ) or ""



    # Combiner sans erreur None
    content = (
            terraform_code
            + "\n"
            + prompt
    ).lower()



    detected = False



    for keyword in TERRAFORM_KEYWORDS:

        if keyword in content:

            detected = True

            logger.info(
                f"Terraform keyword detected: {keyword}"
            )

            break



    if detected:

        logger.info(
            "Terraform infrastructure detected"
        )


        return {

            "is_iac": True,

            "has_iac": True

        }



    else:

        logger.info(
            "Normal user question detected"
        )


        return {

            "is_iac": False,

            "has_iac": False

        }