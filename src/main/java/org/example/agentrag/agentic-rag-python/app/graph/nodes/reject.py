import logging

from app.graph.state import AgentState


logger = logging.getLogger(__name__)


async def reject_node(
        state: AgentState
):


    logger.info(
        "Reject node started"
    )


    return {

        "report":
            "Sorry, I can only help with Azure, Cloud Architecture, Terraform and Infrastructure topics.",


        "status":
            "completed"

    }