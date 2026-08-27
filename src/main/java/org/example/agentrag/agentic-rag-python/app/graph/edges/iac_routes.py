def route_after_iac_detector(state):


    if state.get(
            "is_iac",
            False
    ):

        return "parser"


    return "planner"