"""重新生成部分帧"""

from typing import TypedDict

from langgraph.types import Send
from server.schema.asset import Asset
from server.schema.frame_review import FrameRedoItem
from server.schema.image_generation_request import ImageGenerationRequest
from server.services.image.image_generator import ImageGenerationError, ImageGenerator

from server.schema.frame_review import FrameRedoItem
from server.states import ComicDramaState

from .helpers import frame_key, redo_request


class FrameRedoInput(TypedDict):
    redo_task: dict


# 图的状态里面有一项：pending_frame_redos 存储的是用户输入的重做建议
# 这里做准备，是要准备要重做的帧的生图请求
def prepare_frame_redos(state: ComicDramaState) -> dict:
    # 拿到所有帧所对应的生图请求
    index = dict(state["frame_index"])
    # 从图的状态里面去拿每一帧记录的重做次数
    # {"shot_03:end": 1, "shot_01:start": 2}
    counts = dict(state.get("frame_redo_counts", {}))
    tasks = []
    # 待返工意见，每一项是 FrameRedoItem。人工重做带修改要求；自动检查失败时 comment 为空。
    # [
    #     {
    #         "shot_id": "shot_01",
    #         "frame_type": "end",
    #         "reason": "服装与角色参考图不一致",
    #         "comment": "保持原有服装与辨识特征，保留既定动作和构图",
    #     },
    #     {
    #         "shot_id": "shot_03",
    #         "frame_type": "start",
    #         "reason": "missing_asset",
    #         "comment": "",
    #     },
    # ]
    for raw in state["pending_frame_redos"]:
        item = FrameRedoItem.model_validate(raw)
        # 生成帧标识 -> "shot_01:start"
        key = frame_key(item.shot_id, item.frame_type)
        # 拿到要重做的帧的生图请求
        previous = ImageGenerationRequest.model_validate(index[key])
        # 根据之前的这一帧的生图请求，以及用户输入的这一帧的重做建议
        # 生成新的生图请求
        request = redo_request(previous, item)
        # 往 tasks 里面推东西
        tasks.append(
            {
                "key": key,
                "request": request.model_dump(mode="json"),  # 新的生图请求
                "previous_request_id": previous.request_id,
            }
        )
        # 更新 index 里面对应的生图请求
        index[key] = request.model_dump(mode="json")
        # 这一帧的重做次数+1
        counts[key] = counts.get(key, 0) + 1

    if not tasks:
        raise ValueError("重做计划不能为空")

    # 更新图的状态
    return {
        "frame_index": index,
        "frame_redo_counts": counts,
        "frame_redo_tasks": tasks,  # 最关键的图的状态更新，将重做的帧任务（生图请求）存储到图状态上面
        "pending_frame_redos": [],
        "approved_frames": {},
        "current_stage": "frames_regenerating",
        "events": [f"已准备 {len(tasks)} 个局部单帧任务"],
    }


def dispatch_frame_redos(state: ComicDramaState) -> list[Send]:
    # 从图的状态里面去获取需要重做的任务
    tasks = state.get("frame_redo_tasks", [])

    if state["current_stage"] != "frames_regenerating" or not tasks:
        raise ValueError("必须先保存非空局部计划")

    return [Send("regenerate_frame", {"redo_task": task}) for task in tasks]


def make_regenerate_frame(generator: ImageGenerator):
    def regenerate_frame(state: FrameRedoInput) -> dict:
        # 拿到任务
        task = state["redo_task"]
        # 拿到重做帧的生图请求
        request = ImageGenerationRequest.model_validate(task["request"])
        # 把生图请求转成了 json 格式
        common = request.model_dump(mode="json")

        try:
            image = generator.generate(request)  # 调用生图器做重新生成
            asset = Asset(**common, status="succeeded", image=image)
        except ImageGenerationError as exc:
            asset = Asset(**common, status="failed", error_code=exc.code)
        except (OSError, ValueError):
            asset = Asset(**common, status="failed", error_code="asset_storage_invalid")

        # 更新图的状态
        return {
            "assets": {request.request_id: asset.model_dump(mode="json")},
            "events": [f"局部重做完成：{task['key']} v{request.version}"],
        }

    return regenerate_frame
