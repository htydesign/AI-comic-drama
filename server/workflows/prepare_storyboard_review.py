# 一张子图，负责把当前分镜送到可以人工审核的状态

from typing import Literal

from langgraph.graph import END, START, StateGraph

from server.model.text_model import TextModel

from server.nodes.quality.hard_rules_failed import hard_rules_failed
from server.nodes.quality.make_evaluate_storyboard_quality import (
    make_evaluate_storyboard_quality,
)
from server.nodes.quality.quality_failed import quality_failed
from server.nodes.quality.quality_passed import quality_passed
from server.nodes.revision.make_revise_storyboard import make_revise_storyboard
from server.nodes.revision.revision_exhausted import revision_exhausted
from server.nodes.revision.route_after_failure import route_after_failure
from server.nodes.story_planning.validate_storyboard import validate_storyboard
from server.nodes.revision.revision_stalled import revision_stalled
from server.nodes.revision.route_after_revision import route_after_revision
from server.nodes.quality.route_quality import route_quality
from server.states import ComicDramaState


def route_prepare_entry(
    state: ComicDramaState,
) -> Literal[
    "validate_revised_storyboard",
    "evaluate_storyboard_quality",
    "hard_rules_failed",
]:
    validation = state.get("storyboard_validation")
    if validation is None:
        return "validate_revised_storyboard"
    if validation.is_valid:
        return "evaluate_storyboard_quality"
    return "hard_rules_failed"


def route_validated_storyboard(
    state: ComicDramaState,
) -> Literal["evaluate_storyboard_quality", "hard_rules_failed"]:
    return (
        "evaluate_storyboard_quality"
        if state["storyboard_validation"].is_valid
        else "hard_rules_failed"
    )


def build_prepare_storyboard_review_graph(text_model: TextModel):
    builder = StateGraph(ComicDramaState)

    builder.add_node("hard_rules_failed", hard_rules_failed)
    builder.add_node(
        "evaluate_storyboard_quality", make_evaluate_storyboard_quality(text_model)
    )
    builder.add_node("quality_passed", quality_passed)
    builder.add_node("quality_failed", quality_failed)
    builder.add_node("revise_storyboard", make_revise_storyboard(text_model))
    builder.add_node("validate_revised_storyboard", validate_storyboard)
    builder.add_node("revision_exhausted", revision_exhausted)
    builder.add_node("revision_stalled", revision_stalled)

    builder.add_conditional_edges(START, route_prepare_entry)
    builder.add_conditional_edges("hard_rules_failed", route_after_failure)
    builder.add_conditional_edges("evaluate_storyboard_quality", route_quality)
    builder.add_edge("quality_passed", END)
    builder.add_conditional_edges("quality_failed", route_after_failure)
    builder.add_conditional_edges("revise_storyboard", route_after_revision)
    builder.add_conditional_edges(
        "validate_revised_storyboard", route_validated_storyboard
    )
    builder.add_edge("revision_exhausted", END)
    builder.add_edge("revision_stalled", END)

    return builder.compile()
