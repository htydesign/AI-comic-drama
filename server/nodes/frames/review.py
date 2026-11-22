"""画面检查与人工审核：检查、决定、批准和取消。"""

from typing import Literal

from langgraph.types import Command, interrupt
from pydantic import ValidationError

from server.schema.frame_review import FrameReview
from server.schema.image_generation_request import ImageGenerationRequest
from server.states import ComicDramaState
from server.storage.asset_storage import AssetStore


from .helpers import (
    MAX_FRAME_REDOS,
    frame_key,
    frame_project_id,
    inspect_frames,
    redo_request,
    snapshot_token,
)


def make_check_frames(store: AssetStore):
    def check_frames(
        state: ComicDramaState,
    ) -> Command[Literal["prepare_frame_redos", "review_frames"]]:
        index, frames, failed = inspect_frames(state, store)
        counts = state.get("frame_redo_counts", {})
        exhausted = [
            frame_key(x["shot_id"], x["frame_type"])
            for x in failed
            if counts.get(frame_key(x["shot_id"], x["frame_type"]), 0)
            >= MAX_FRAME_REDOS
        ]
        round_number = state.get("frame_review_round", 0) + 1
        token = snapshot_token(
            frame_project_id(state), state["approved_version"], round_number, frames
        )
        # 有一项耗尽就暂停，保留其他项的额度；不把整部作品无限拖进生成循环。
        auto_redo = bool(failed) and not exhausted
        return Command(
            goto="prepare_frame_redos" if auto_redo else "review_frames",
            update={
                "frame_index": index,
                "frame_check": {
                    "frames": frames,
                    "failed": failed,
                    "is_complete": not failed,
                    "exhausted_keys": exhausted,
                },
                "pending_frame_redos": failed if auto_redo else [],
                "frame_review_round": round_number,
                "frame_review_token": token,
                "frame_review_error": None,
                "approved_frames": {},
                "current_stage": (
                    "frame_redo_pending"
                    if auto_redo
                    else (
                        "frame_redo_exhausted" if exhausted else "frames_review_pending"
                    )
                ),
                "events": [f"画面检查：失败 {len(failed)}，耗尽 {len(exhausted)}"],
            },
        )

    return check_frames


def make_review_frames(store: AssetStore):
    def review_frames(
        state: ComicDramaState,
    ) -> Command[
        Literal[
            "frames_approved",
            "prepare_frame_redos",
            "frames_cancelled",
            "review_frames",
        ]
    ]:
        # 【重要】节点恢复时从头重放。中断前只组装载荷，不生成、不写文件，
        # 每次调用仅中断一次；无效答案先保存错误，再通过图路由回本节点。
        raw = interrupt(
            {
                "project_id": frame_project_id(state),
                "version": state["approved_version"],
                "review_token": state["frame_review_token"],
                "error": state.get("frame_review_error"),
                "automatic_check": state["frame_check"],
                "allowed_actions": ["approve", "regenerate", "cancel"],
                "max_redos_per_frame": MAX_FRAME_REDOS,
                "redo_counts": state.get("frame_redo_counts", {}),
            }
        )
        try:
            review = FrameReview.model_validate(raw)
            if review.command_id in state.get("frame_command_ids", []):
                raise ValueError("该审核命令已处理，请刷新当前审核载荷后再提交")
            if (
                review.version != state["approved_version"]
                or review.review_token != state["frame_review_token"]
            ):
                raise ValueError("审核快照已过期，请使用当前 version 和 review_token")
            # 取消不要求损坏文件可恢复；通过和重做必须核对用户正在看的快照。
            if review.action != "cancel":
                _, frames, _ = inspect_frames(state, store)
                current = snapshot_token(
                    frame_project_id(state),
                    state["approved_version"],
                    state["frame_review_round"],
                    frames,
                )
                if current != review.review_token:
                    raise ValueError(
                        "审核期间文件发生变化，请取消并检查档案；不能批准旧快照"
                    )
            if review.action == "approve" and not state["frame_check"]["is_complete"]:
                raise ValueError("素材不完整或重做额度耗尽，不能批准；可取消作品")
            unique = {}
            for item in review.items:
                key = frame_key(item.shot_id, item.frame_type)
                if key not in state["frame_index"]:
                    raise ValueError("重做项引用了未知镜头或帧")
                if key in unique and unique[key] != item.model_dump(mode="json"):
                    raise ValueError("同一帧存在冲突意见，请合并后提交")
                if state.get("frame_redo_counts", {}).get(key, 0) >= MAX_FRAME_REDOS:
                    raise ValueError("该帧重做次数已达上限，可取消作品并人工检查")
                # 提前验证修改意见长度与新请求 Schema，错误在付费计划落盘前重新提问。
                redo_request(
                    ImageGenerationRequest.model_validate(state["frame_index"][key]),
                    item,
                )
                unique[key] = item.model_dump(mode="json")
        except (ValidationError, ValueError) as exc:
            # 【重要】错误进入 Checkpoint，然后 goto 自己产生新的审核任务。
            # 不在节点内 while interrupt，避免恢复时重放此前所有无效答案。
            return Command(
                goto="review_frames", update={"frame_review_error": str(exc)}
            )
        target = {
            "approve": "frames_approved",
            "regenerate": "prepare_frame_redos",
            "cancel": "frames_cancelled",
        }[review.action]
        return Command(
            goto=target,
            update={
                "frame_review_error": None,
                "frame_review_result": review.model_dump(mode="json"),
                "frame_command_ids": [
                    *state.get("frame_command_ids", []),
                    review.command_id,
                ],
                "pending_frame_redos": list(unique.values()),
                "events": [f"画面审核决定：{review.action}"],
            },
        )

    return review_frames


def make_approve_frames(store: AssetStore):
    def frames_approved(state: ComicDramaState) -> dict:
        _, frames, failed = inspect_frames(state, store)
        token = snapshot_token(
            frame_project_id(state),
            state["approved_version"],
            state["frame_review_round"],
            frames,
        )
        if (
            failed
            or token != state["frame_review_token"]
            or state["frame_review_result"]["action"] != "approve"
        ):
            raise ValueError("批准前素材再次校验失败")
        # 视频阶段只能消费这个明确锁定的清单，不能遍历历史 assets 取最大版本。
        return {
            "approved_frames": {x["key"]: x for x in frames},
            "current_stage": "frames_approved",
            "events": ["首尾帧版本已批准，等待视频阶段"],
        }

    return frames_approved


def frames_cancelled(state: ComicDramaState) -> dict:
    return {
        "approved_frames": {},
        "current_stage": "frames_cancelled",
        "stop_reason": "frames_cancelled_by_user",
        "events": ["用户取消画面制作"],
    }
