from langgraph.graph import (
    StateGraph,
    START,
    END
)


from app.graph.state import AgentState


from app.graph.nodes.iac_detector import iac_detector_node
from app.graph.nodes.parser import parser_node
from app.graph.nodes.planner import planner_node
from app.graph.nodes.retriever import retriever_node
from app.graph.nodes.reranker import reranker_node
from app.graph.nodes.validator import validator_node
from app.graph.nodes.fixer import fixer_node
from app.graph.nodes.reporter import reporter_node
from app.graph.nodes.chat import chat_node
from app.graph.nodes.reject import reject_node



from app.graph.edges.iac_routes import (
    route_after_iac_detector
)


from app.graph.edges.conditions import (
    route_after_planner,
    route_after_reranker,
    should_fix
)



def create_workflow():



    graph = StateGraph(
        AgentState
    )



    # ==============================
    # Nodes
    # ==============================


    graph.add_node(
        "iac_detector",
        iac_detector_node
    )


    graph.add_node(
        "parser",
        parser_node
    )


    graph.add_node(
        "planner",
        planner_node
    )


    graph.add_node(
        "retriever",
        retriever_node
    )


    graph.add_node(
        "reranker",
        reranker_node
    )


    graph.add_node(
        "validator",
        validator_node
    )


    graph.add_node(
        "fixer",
        fixer_node
    )


    graph.add_node(
        "reporter",
        reporter_node
    )


    graph.add_node(
        "chat",
        chat_node
    )


    graph.add_node(
        "reject",
        reject_node
    )



    # ==============================
    # START
    # ==============================


    graph.add_edge(
        START,
        "iac_detector"
    )



    # ==============================
    # IaC detector
    # ==============================


    graph.add_conditional_edges(

        "iac_detector",

        route_after_iac_detector,


        {

            "parser":
                "parser",


            "planner":
                "planner"

        }

    )



    # ==============================
    # IaC flow
    # ==============================


    graph.add_edge(

        "parser",

        "retriever"

    )


    graph.add_edge(

        "retriever",

        "reranker"

    )


    graph.add_conditional_edges(

        "reranker",

        route_after_reranker,


        {

            "validator":
                "validator",


            "reporter":
                "reporter"

        }

    )



    graph.add_conditional_edges(

        "validator",

        should_fix,


        {

            "fixer":
                "fixer",


            "reporter":
                "reporter"

        }

    )



    graph.add_edge(

        "fixer",

        "reporter"

    )



    # ==============================
    # Normal RAG
    # ==============================


    graph.add_conditional_edges(

        "planner",

        route_after_planner,


        {

            "chat":
                "chat",


            "retriever":
                "retriever",


            "parser":
                "parser",


            "reject":
                "reject"

        }

    )



    # ==============================
    # END
    # ==============================


    graph.add_edge(

        "reporter",

        END

    )


    graph.add_edge(

        "chat",

        END

    )


    graph.add_edge(

        "reject",

        END

    )



    return graph.compile()



workflow = create_workflow()