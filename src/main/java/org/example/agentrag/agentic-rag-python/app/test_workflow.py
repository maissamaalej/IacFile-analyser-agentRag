import asyncio

from app.graph.graph_workflow import workflow


async def run_test(prompt: str, terraform_code=None):

    print("\n")
    print("=" * 80)
    print("USER QUERY")
    print("=" * 80)

    print(prompt)


    initial_state = {

        # Conversation
        "messages": [],


        # User
        "user_id": 1,
        "chat_id": 1,


        # Input
        "prompt": prompt,

        "terraform_code": terraform_code,


        # Planner
        "task": None,

        "plan": [],

        "current_query": None,


        # Infrastructure
        "infrastructure": {},


        # Retrieval
        "retrieved_documents": [],

        "reranked_documents": [],


        # Validation
        "findings": [],

        "recommendations": [],

        "fix_requested": False,

        "validation_summary": None,


        # Fixer

        "fixed_terraform": None,

        "fix_summary": None,

        "changes": [],


        # Reporter

        "report": None,


        # Metadata

        "score": None,

        "status": "starting",

        "error": None
    }


    result = await workflow.ainvoke(
        initial_state
    )


    print("\n")
    print("=" * 80)
    print("FINAL STATE")
    print("=" * 80)


    print("STATUS:")
    print(result.get("status"))


    print("\nTASK:")
    print(result.get("task"))


    print("\nACTION:")
    print(result.get("action"))


    print("\nPLAN:")
    print(result.get("plan"))


    print("\nREPORT:")
    print(result.get("report"))


    print("\nFIXED TERRAFORM:")
    print(result.get("fixed_terraform"))



async def main():


    # =========================
    # TEST 1
    # Conversation
    # =========================

    await run_test(
        "helloooo"
    )

    await run_test(
        "what are azure best practices?"
    )



    # =========================
    # TEST 2
    # RAG
    # =========================

    await run_test(

        """Analyze this Terraform code and find security issues. 
    I want recommendations based on Azure security best practices.

    Terraform:

    resource "azurerm_storage_account" "example" {

        name                     = "mystorageaccount123"
    resource_group_name      = azurerm_resource_group.example.name
    location                 = "West Europe"

    account_tier             = "Standard"
    account_replication_type = "LRS"

    public_network_access_enabled = true

    min_tls_version = "TLS1_0"

    } """

    )









if __name__ == "__main__":

    asyncio.run(main())