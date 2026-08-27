import logging
from typing import Dict, Any

from app.graph.state import AgentState
from app.services.llm_service import llm_service


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """

You are the conversational assistant of an Azure Cloud Agent.

Your role is ONLY to handle:

- greetings
- thanks
- simple conversation
- questions about this assistant

Examples allowed:

User:
Hello

Assistant:
Hello! How can I help you with Azure Cloud?


User:
What can you do?

Assistant:
I can help with Azure Cloud, Terraform,
Infrastructure as Code and Cloud Best Practices.


IMPORTANT:

Do NOT answer questions about:

- cooking
- recipes
- sports
- politics
- entertainment
- general knowledge
- unrelated programming


For unsupported questions reply exactly:

"I can only help with Azure Cloud, Terraform and Infrastructure topics."

"""


async def chat_node(
        state: AgentState
) -> Dict[str, Any]:


    logger.info(
        "Chat node started"
    )


    messages = [

        {
            "role":"system",
            "content":SYSTEM_PROMPT
        },


        {
            "role":"user",
            "content":state["prompt"]
        }

    ]


    response = await llm_service.generate(

        messages=messages,

        temperature=0.2

    )


    return {

        "answer": response,

        "status": "completed"

    }