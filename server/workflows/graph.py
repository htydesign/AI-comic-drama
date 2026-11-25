import os
from pathlib import Path

from fastapi import concurrency
from langgraph.graph import END, START, StateGraph
from server.nodes.frames.generation import (
    ShotFrameInput,
    dispatch_shot_frames,
    make_collect_shot_frames,
    make_generate_shot_frames,
    make_prepare_shot_frames,
    route_after_references,
)
from server.nodes.frames.regeneration import (
    FrameRedoInput,
    dispatch_frame_redos,
    make_regenerate_frame,
    prepare_frame_redos,
)
from server.nodes.frames.review import (
    frames_cancelled,
    make_approve_frames,
    make_check_frames,
    make_review_frames,
)
from server.nodes.references.collect_reference_assets import collect_reference_assets
from server.nodes.references.make_prepare_visual_bible import make_prepare_visual_bible
from server.nodes.references.make_reference_node import make_reference_node
from server.nodes.review.make_revise_from_review import make_revise_from_review
from server.nodes.review.review_storyboard import review_storyboard
from server.nodes.revision.initialize_revision import initialize_revision
from server.nodes.video.batch import (
    make_compose_videos,
    prepare_videos,
    dispatch_videos,
)
from server.services.image.build_image_generator import (
    ImageRuntimeConfig,
    build_image_generator_from_env,
)
from server.services.image.image_generator import ImageGenerator
from server.services.video.video_service import VideoService
from server.states import ComicDramaState
from server.model.text_model import TextModel
from server.model.build_text_model import build_text_model
from server.storage.asset_storage import AssetStore
from server.workflows.shot_video import build_shot_video_graph
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
    frame_store: AssetStore | None = None,
    max_concurrency: int | None = None,
    checkpointer=None,
    video_service: VideoService | None = None,
):
    # 创建图像生成器
    if image_generator is None:
        # 创建图像生成器
        config = ImageRuntimeConfig.from_env()  # 从环境变量里面读取配置
        image_generator = build_image_generator_from_env()  # 创建图像生成器
        # 就是一个标识【模型厂商:模型】
        generation_profile = f"{config.provider}:{config.model if config.provider == 'ark' else 'fake-image-v1'}"
    elif generation_profile is None:
        raise ValueError("注入图像生成器时必须明确 generation_profile")

    # 处理 frame_store
    if frame_store is None:
        frame_store = AssetStore(Path(__file__).resolve().parents[2])

    # 处理 max_concurrency
    concurrency = (
        max_concurrency
        if max_concurrency is not None
        else int(os.getenv("SHOT_FRAME_MAX_CONCURRENCY", "3"))
    )

    if (
        isinstance(concurrency, bool)
        or not isinstance(concurrency, int)
        or concurrency < 1
    ):
        raise ValueError("max_concurrency 必须为正整数")

    # 初始化 video_service 的值
    video_service = video_service or VideoService(frame_store)

    # 创建子图
    planning_graph = build_story_planning_graph(text_model)  # 创建子图1
    prepare_graph = build_prepare_storyboard_review_graph(text_model)  # 创建子图2

    # 新增一个节点（这里使用了第1张子图）
    def story_planning(state: ComicDramaState) -> dict[str, object]:
        # 调用子图
        child_result = planning_graph.invoke(state)

        return {
            **child_result,
            "events": child_result["events"][len(state["events"]) :],
        }

    # 新增一个节点（这里使用了第2张子图）
    def prepare_storyboard_review(state: ComicDramaState) -> dict[str, object]:
        # 调用子图
        child_result = prepare_graph.invoke(state)

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
    # 首次按镜头派发，局部返工按单帧派发。
    builder.add_node(
        "prepare_shot_frames", make_prepare_shot_frames(frame_store, generation_profile)
    )
    builder.add_node(
        "generate_shot_frames",
        make_generate_shot_frames(image_generator),
        input_schema=ShotFrameInput,
    )
    builder.add_node("collect_shot_frames", make_collect_shot_frames(frame_store))
    builder.add_node("check_frames", make_check_frames(frame_store))
    builder.add_node("review_frames", make_review_frames(frame_store))
    builder.add_node("prepare_frame_redos", prepare_frame_redos)
    builder.add_node(
        "regenerate_frame",
        make_regenerate_frame(image_generator),
        input_schema=FrameRedoInput,
    )
    builder.add_node("frames_approved", make_approve_frames(frame_store))
    builder.add_node("frames_cancelled", frames_cancelled)
    builder.add_node("prepare_videos", prepare_videos)
    # build_shot_video_graph() 就是在创建 generate_video 子图
    builder.add_node("generate_video", build_shot_video_graph(video_service))
    builder.add_node("compose_videos", make_compose_videos(video_service))

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
    builder.add_conditional_edges(
        "collect_reference_assets",
        route_after_references,
        path_map=["prepare_shot_frames", END],
    )
    builder.add_conditional_edges(
        "prepare_shot_frames",
        dispatch_shot_frames,
        path_map=["generate_shot_frames"],
    )
    builder.add_edge("generate_shot_frames", "collect_shot_frames")
    builder.add_edge("collect_shot_frames", "check_frames")
    # 检查与审核节点通过 Command 选择唯一出口，不再添加静态出边。
    builder.add_conditional_edges(
        "prepare_frame_redos",
        dispatch_frame_redos,
        path_map=["regenerate_frame"],
    )
    builder.add_edge("regenerate_frame", "check_frames")
    builder.add_edge("frames_approved", "prepare_videos")
    builder.add_conditional_edges(
        "prepare_videos", dispatch_videos, ["generate_video", END]
    )
    builder.add_edge("generate_video", "compose_videos")
    builder.add_edge("compose_videos", END)
    builder.add_edge("frames_cancelled", END)
    builder.add_edge("storyboard_cancelled", END)
    return builder.compile(checkpointer=checkpointer).with_config(
        {"max_concurrency": concurrency}
    )


graph = build_graph(build_text_model())

test = """
{
  "raw_requirement": "深夜的办公室里，程序员小林正在修改一款漫画应用。零点到来时，他设计的漫画角色阿沐突然从屏幕中走了出来。",
  "current_stage": "submitted",
  "events": [],
  "max_revisions": 2
}
"""
