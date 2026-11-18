from langfuse.types import TraceContext
from langgraph.graph import END, START, StateGraph
from server.nodes.quality.hard_rules_failed import hard_rules_failed
from server.nodes.quality.make_evaluate_storyboard_quality import (
    make_evaluate_storyboard_quality,
)
from server.nodes.quality.quality_failed import quality_failed
from server.nodes.quality.quality_passed import quality_passed
from server.nodes.quality.route_quality import route_quality

from server.nodes.revision.initialize_revision import initialize_revision
from server.nodes.revision.make_revise_storyboard import make_revise_storyboard
from server.nodes.revision.revision_exhausted import revision_exhausted
from server.nodes.revision.revision_stalled import revision_stalled
from server.nodes.revision.route_after_failure import route_after_failure
from server.nodes.revision.route_after_revision import route_after_revision
from server.nodes.story_planning.validate_storyboard import validate_storyboard
from server.states import ComicDramaState
from server.model.text_model import TextModel
from server.model.build_text_model import build_text_model
from server.utils.trace_wrapper import trace_wrapper
from server.workflows.story_planning import build_story_planning_graph


def build_graph(text_model: TextModel):

    planning_graph = build_story_planning_graph(text_model)

    async def story_planning(state: ComicDramaState) -> dict[str, object]:
        child_result = await planning_graph.ainvoke(state)

        return {
            **child_result,
            "events": child_result["events"][len(state["events"]) :],
        }

    builder = StateGraph(ComicDramaState)

    builder.add_node("story_planning", story_planning)
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
    builder.add_node("initialize_revision", initialize_revision)

    builder.add_edge(START, "story_planning")
    builder.add_edge("story_planning", "initialize_revision")
    builder.add_conditional_edges(
        "initialize_revision",
        lambda state: (
            "evaluate_storyboard_quality"
            if state["storyboard_validation"].is_valid
            else "hard_rules_failed"
        ),
        path_map=["evaluate_storyboard_quality", "hard_rules_failed"],
    )
    builder.add_conditional_edges("hard_rules_failed", route_after_failure)
    builder.add_conditional_edges("evaluate_storyboard_quality", route_quality)
    builder.add_edge("quality_passed", END)
    builder.add_conditional_edges("quality_failed", route_after_failure)
    builder.add_conditional_edges("revise_storyboard", route_after_revision)
    builder.add_conditional_edges(
        "validate_revised_storyboard",
        lambda state: (
            "evaluate_storyboard_quality"
            if state["storyboard_validation"].is_valid
            else "hard_rules_failed"
        ),
        path_map=["evaluate_storyboard_quality", "hard_rules_failed"],
    )
    builder.add_edge("revision_exhausted", END)
    builder.add_edge("revision_stalled", END)

    return builder.compile()


async def graph_factory():
    return build_graph(build_text_model())


graph = trace_wrapper(graph_factory)

test = """
{
  "raw_requirement": "深夜的办公室里，程序员小林正在修改一款漫画应用。零点到来时，他设计的漫画角色阿沐突然从屏幕中走了出来。",
  "current_stage": "submitted",
  "events": [],
  "max_revisions": 2
}
"""
