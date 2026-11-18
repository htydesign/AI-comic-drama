from typing import Literal

from langgraph.types import Command, interrupt
from pydantic import ValidationError

from server.schema import StoryboardReview
from server.states import ComicDramaState


def review_storyboard(
    state: ComicDramaState,
) -> Command[
    Literal[
        "storyboard_approved",
        "revise_from_review",
        "storyboard_cancelled",
        "review_storyboard",
    ]
]:
    # 恢复时从节点开头重放；interrupt 前只整理材料，不调用模型。

    # 取出质检报告
    report = state.get("quality_report")
    # 中断，等待人工审核，拿到用户的审核意见
    raw = interrupt(
        {
            "title": state["requirement"].title,
            "story_summary": state["story_outline"].theme,
            "version": state["revision_count"],
            "review_reason": state["current_stage"],
            "stop_reason": state.get("stop_reason"),
            "storyboard": [
                shot.model_dump(mode="json") for shot in state["storyboard"]
            ],
            "quality_report": report.model_dump(mode="json") if report else None,
            "allowed_actions": ["approve", "revise", "cancel"],
            "error": state.get("review_error"),
        }
    )
    # 验证用户的审核意见
    try:
        review = StoryboardReview.model_validate(raw)
        if review.version != state["revision_count"]:
            raise ValueError(
                f"审核版本已过期：当前 v{state['revision_count']}，收到 v{review.version}"
            )
        known_ids = {shot.shot_id for shot in state["storyboard"]}
        unknown = set(review.shot_ids) - known_ids
        if unknown:
            raise ValueError(f"审核意见引用了未知分镜：{sorted(unknown)}")
    except (ValidationError, ValueError) as exc:
        return Command(goto="review_storyboard", update={"review_error": str(exc)})
    target = {
        "approve": "storyboard_approved",
        "revise": "revise_from_review",
        "cancel": "storyboard_cancelled",
    }[review.action]
    return Command(
        goto=target,
        update={
            "review_result": review,
            "review_error": None,
            "events": [f"已收到人工审核命令：{review.action}"],
        },
    )
