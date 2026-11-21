from langgraph.graph import END, START, StateGraph
from server.nodes.references.collect_reference_assets import collect_reference_assets
from server.nodes.references.make_prepare_visual_bible import make_prepare_visual_bible
from server.nodes.references.make_reference_node import make_reference_node
from server.nodes.review.make_revise_from_review import make_revise_from_review
from server.nodes.review.review_storyboard import review_storyboard
from server.nodes.revision.initialize_revision import initialize_revision
from server.services.image.build_image_generator import (
    ImageRuntimeConfig,
    build_image_generator_from_env,
)
from server.services.image.image_generator import ImageGenerator
from server.states import ComicDramaState
from server.model.text_model import TextModel
from server.model.build_text_model import build_text_model
from server.workflows.story_planning import build_story_planning_graph
from server.nodes.review.storyboard_approved import storyboard_approved
from server.nodes.review.storyboard_cancelled import storyboard_cancelled
from server.workflows.prepare_storyboard_review import (
    build_prepare_storyboard_review_graph,
)


def build_graph(
    text_model: TextModel,
    *,
    image_generator: ImageGenerator | None = None,
    generation_profile: str | None = None,
    checkpointer=None,
):
    if image_generator is None:
        config = ImageRuntimeConfig.from_env()
        image_generator = build_image_generator_from_env()
        generation_profile = f"{config.provider}:{config.model if config.provider == 'ark' else 'fake-image-v1'}"
    elif generation_profile is None:
        raise ValueError("注入图像生成器时必须明确 generation_profile")

    planning_graph = build_story_planning_graph(text_model)
    prepare_graph = build_prepare_storyboard_review_graph(text_model)

    async def story_planning(state: ComicDramaState) -> dict[str, object]:
        child_result = await planning_graph.ainvoke(state)

        return {
            **child_result,
            "events": child_result["events"][len(state["events"]) :],
        }

    async def prepare_storyboard_review(state: ComicDramaState) -> dict[str, object]:
        # 子图内包含 async 节点（evaluate_storyboard_quality / revise_storyboard），
        # 必须以异步 API 调用，否则同步 invoke 会因无法在线程池执行协程而抛 TypeError。
        child_result = await prepare_graph.ainvoke(state)

        return {
            **child_result,
            "events": child_result["events"][len(state["events"]) :],
        }

    builder = StateGraph(ComicDramaState)

    # 加点
    builder.add_node("story_planning", story_planning)
    builder.add_node("initialize_revision", initialize_revision)
    builder.add_node("prepare_storyboard_review", prepare_storyboard_review)
    builder.add_node("review_storyboard", review_storyboard)
    builder.add_node("revise_from_review", make_revise_from_review(text_model))
    builder.add_node("storyboard_approved", storyboard_approved)
    builder.add_node("storyboard_cancelled", storyboard_cancelled)
    builder.add_node(
        "prepare_visual_bible", make_prepare_visual_bible(generation_profile)
    )
    builder.add_node(
        "generate_character_references",
        make_reference_node(image_generator, purpose="character_reference"),
    )
    builder.add_node(
        "generate_scene_references",
        make_reference_node(image_generator, purpose="scene_reference"),
    )
    builder.add_node("collect_reference_assets", collect_reference_assets)

    # 连边
    builder.add_edge(START, "story_planning")
    builder.add_edge("story_planning", "initialize_revision")
    builder.add_edge("initialize_revision", "prepare_storyboard_review")
    builder.add_edge("prepare_storyboard_review", "review_storyboard")

    # review_storyboard 由 Command 选择唯一业务路径，不再添加静态出口。
    builder.add_conditional_edges(
        "revise_from_review",
        lambda state: (
            "review_storyboard"
            if state["current_stage"] == "revision_stalled"
            else "prepare_storyboard_review"
        ),
        path_map=["review_storyboard", "prepare_storyboard_review"],
    )
    builder.add_edge("storyboard_approved", "prepare_visual_bible")
    builder.add_edge("prepare_visual_bible", "generate_character_references")
    builder.add_edge("prepare_visual_bible", "generate_scene_references")
    builder.add_edge(
        ["generate_character_references", "generate_scene_references"],
        "collect_reference_assets",
    )
    builder.add_edge("collect_reference_assets", END)
    builder.add_edge("storyboard_cancelled", END)
    return builder.compile(checkpointer=checkpointer)


graph = build_graph(build_text_model())

test = """
{
  "raw_requirement": "深夜的办公室里，程序员小林正在修改一款漫画应用。零点到来时，他设计的漫画角色阿沐突然从屏幕中走了出来。",
  "current_stage": "submitted",
  "events": [],
  "max_revisions": 2
}
"""
