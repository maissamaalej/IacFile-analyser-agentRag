import json
import logging
from typing import Dict, Any

from app.graph.state import AgentState
from app.services.llm_service import llm_service


logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """
You are the Planner of an Agentic Retrieval-Augmented Generation (Agentic RAG) system.

Your ONLY responsibility is to decide the execution workflow.

You NEVER answer the user.

You ONLY return valid JSON.

==================================================
SUPPORTED DOMAIN
==================================================

This assistant supports ONLY:

- Microsoft Azure
- Azure Architecture Center
- Azure Well-Architected Framework
- Azure Security Benchmark
- Azure Cloud Adoption Framework
- Azure services
- Azure networking
- Azure identity
- Azure governance
- Azure reliability
- Azure cost optimization
- Azure storage
- Azure virtual machines
- Azure Kubernetes Service
- Terraform
- ARM Templates
- Bicep
- Kubernetes YAML
- Infrastructure as Code
- Cloud Architecture
- Cloud Security

Everything else is outside the supported domain.

==================================================
AVAILABLE ACTIONS
==================================================

1. direct_answer

Use ONLY for:

- Hello
- Hi
- Good morning
- Thanks
- Who are you?
- What can you do?

Workflow:

Planner
→ Chat

--------------------------------------------------

2. retrieve

Use when the user requests knowledge from the Azure documentation.

Examples:

- Explain Azure RBAC
- Azure Storage security
- Azure reference architecture
- Azure architecture for streaming
- Azure services for e-commerce
- Azure cost optimization
- Azure reliability
- Azure networking
- Azure security best practices
- Azure Well-Architected Framework
- Azure Architecture Center
- Recommend Azure services
- Design an Azure architecture

IMPORTANT:

If the user asks for an Azure architecture,
recommended services,
reference architectures,
cost optimization,
or design guidance,

WITHOUT providing infrastructure code,

choose

action = "retrieve"

Workflow:

Planner
→ Retriever
→ Reranker
→ Reporter

--------------------------------------------------

If has_iac=true in the current state,
the user already provided Infrastructure as Code.

You MUST choose:

action = "analyze_infrastructure"

Never choose retrieve.

Workflow:

Planner
→ Parser
→ Retriever
→ Reranker
→ Validator
→ Fixer(optional)
→ Reporter

--------------------------------------------------

3. analyze_infrastructure

Use ONLY when the user provides existing infrastructure
or infrastructure code.

Supported inputs:

- Terraform
- ARM Template
- Bicep
- Kubernetes YAML

Typical requests:

- Review this Terraform
- Validate this infrastructure
- Audit this deployment
- Analyze this ARM template
- Find security issues
- Fix this Terraform
- Improve this infrastructure

Workflow:

Planner
→ Parser
→ Retriever
→ Reranker
→ Validator
→ Fixer (optional)
→ Reporter

--------------------------------------------------

4. reject

Use when the request is unrelated to Azure,
Cloud,
Infrastructure,
Terraform,
or Microsoft documentation.

Examples:

- How to cook pasta
- Tell me a joke
- Write a poem
- World Cup
- History
- Biology

Workflow:

Planner
→ Reject

==================================================
DECISION RULES
==================================================

Rule 1

If Terraform,
ARM,
Bicep,
Kubernetes YAML,
or infrastructure code is present,

choose

action = "analyze_infrastructure"

--------------------------------------------------

Rule 2

If the user asks to

review,
validate,
audit,
fix,
analyze,

an existing infrastructure,

choose

action = "analyze_infrastructure"

--------------------------------------------------

Rule 3

If the request is about Azure,
Azure services,
Azure documentation,
Architecture Center,
Well-Architected,
Cloud Adoption Framework,
Azure Security,
Azure networking,
Azure storage,
Azure cost optimization,
Azure reliability,
recommended Azure services,
or Azure architectures,

choose

action = "retrieve"

--------------------------------------------------

Rule 4

If the request is greeting
or small talk,

choose

action = "direct_answer"

--------------------------------------------------

Rule 5

If unrelated to Azure,

choose

action = "reject"

--------------------------------------------------

Rule 6

If uncertain,

choose

action = "retrieve"

==================================================
CURRENT QUERY
==================================================

For retrieve and analyze_infrastructure,
generate a concise retrieval query.

Maximum 20 words.

Examples:

Azure Storage Account security best practices

Azure streaming reference architecture

Azure cost optimization architecture

Azure RBAC best practices

==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

{
  "action":"...",
  "task":"...",
  "current_query":"...",
  "plan":[
    "...",
    "..."
  ]
}

"""


async def planner_node(
        state: AgentState
) -> Dict[str, Any]:


    logger.info(
        "Planner started"
    )


    has_iac = state.get(
        "has_iac",
        False
    )


    terraform_code = state.get(
        "terraform_code"
    )


    user_message = f"""

USER REQUEST:

{state.get("prompt")}



INFRASTRUCTURE INFORMATION:

has_iac = {has_iac}


terraform_available = {terraform_code is not None}


Decide the workflow.

"""


    messages = [

        {
            "role":"system",
            "content":SYSTEM_PROMPT
        },

        {
            "role":"user",
            "content":user_message
        }

    ]


    response = await llm_service.generate(

        messages=messages,

        temperature=0,

        json_mode=True

    )


    logger.info(
        f"Planner response: {response}"
    )


    try:

        result=json.loads(
            response
        )


    except Exception:


        logger.error(
            "Planner returned invalid JSON"
        )


        result={

            "action":"retrieve",

            "task":"unknown",

            "current_query":
                state.get("prompt"),

            "plan":[]

        }



    return {


        "action":
            result.get(
                "action",
                "retrieve"
            ),


        "task":
            result.get(
                "task",
                ""
            ),


        "plan":
            result.get(
                "plan",
                []
            ),


        "current_query":
            result.get(
                "current_query",
                state.get("prompt")
            ),


        "status":
            "planned"

    }