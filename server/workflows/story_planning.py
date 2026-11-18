from typing import Literal

from langgraph.graph import END, START, StateGraph

from server.nodes import (
    receive_idea,
    make_analyze_requirement,
    make_generate_scenes,
    make_generate_characters,
    make_generate_story_outline,
    finish_planning,
    storyboard_ready,
)
from server.nodes.story_planning.make_generate_storyboard import (
    make_generate_storyboard,
)
from server.nodes.story_planning.storyboard_invalid import storyboard_invalid
from server.nodes.story_planning.validate_storyboard import validate_storyboard
from server.states import ComicDramaState
from server.model.text_model import TextModel
from server.model.build_text_model import build_text_model


def route_storyboard(
    state: ComicDramaState,
) -> Literal["storyboard_ready", "storyboard_invalid"]:

    is_valid = state["storyboard_validation"].is_valid

    return "storyboard_ready" if is_valid else "storyboard_invalid"


def build_story_planning_graph(text_model: TextModel):

    builder = StateGraph(ComicDramaState)

    builder.add_node("receive_idea", receive_idea)
    builder.add_node("make_analyze_requirement", make_analyze_requirement(text_model))
    builder.add_node(
        "make_generate_story_outline", make_generate_story_outline(text_model)
    )
    builder.add_node("make_generate_scenes", make_generate_scenes(text_model))
    builder.add_node("make_generate_characters", make_generate_characters(text_model))
    builder.add_node("finish_planning", finish_planning)
    builder.add_node("generate_storyboard", make_generate_storyboard(text_model))
    builder.add_node("validate_storyboard", validate_storyboard)
    builder.add_node("storyboard_ready", storyboard_ready)
    builder.add_node("storyboard_invalid", storyboard_invalid)

    builder.add_edge(START, "receive_idea")
    builder.add_edge("receive_idea", "make_analyze_requirement")
    builder.add_edge("make_analyze_requirement", "make_generate_story_outline")
    builder.add_edge("make_generate_story_outline", "make_generate_scenes")
    builder.add_edge("make_generate_story_outline", "make_generate_characters")
    builder.add_edge("make_generate_scenes", "finish_planning")
    builder.add_edge("make_generate_characters", "finish_planning")
    builder.add_edge("finish_planning", "generate_storyboard")
    builder.add_edge("generate_storyboard", "validate_storyboard")
    builder.add_conditional_edges("validate_storyboard", route_storyboard)
    builder.add_edge("storyboard_ready", END)
    builder.add_edge("storyboard_invalid", END)

    return builder.compile()
