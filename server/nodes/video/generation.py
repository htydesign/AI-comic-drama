"""单分镜视频任务的提交、查询、等待和下载节点。"""

from typing import TypedDict

from arkruntime._exceptions import ArkError
from langgraph.types import interrupt

from server.services.video.video_service import VideoService


# 定义子图的状态：该状态仅在子图里面使用
class ShotVideoState(TypedDict, total=False):
    job: dict
    task_id: str
    queries: int  # 存储查询的次数
    status: str  # 视频生成任务的完成状态
    video_url: str  # 视频生成的 url（远端，方舟那边远程的 url） "video_url": "https://ark-content-generation-cn-beijing.tos-cn-beijing.volces.com/xxx.mp4"
    video_results: dict[str, dict]  # 回头会汇总到父图状态里面的结果


# 指定子图里面的哪些状态要汇总到父图状态里面
class ShotVideoOutput(TypedDict):
    video_results: dict[str, dict]


# 这个是一个工具节点
# 负责将生成的视频结果包装成一个能合并到父图状态里面的的 video_results
# state 是子图状态
def shot_video_result(state, *, path=None, error=None):
    # 得到分镜的 id
    shot_id = state["job"]["shot_id"]

    return {
        "video_results": {
            shot_id: {
                "task_id": state.get("task_id"),
                "path": path,
                "error": error,
            }
        }
    }


# 向方舟提交视频生成任务，通过调用 VideoService 来提交
def make_submit_shot_video(service: VideoService):
    # 通过闭包的形式把 VideoService（视频生成服务）注入进来
    def submit(state):
        try:
            # 更新子图的状态
            return {"task_id": service.submit(state["job"]), "queries": 0}
        except (ArkError, OSError, ValueError, KeyError) as exc:
            # 如果出错，返回一个类似于
            # {"video_results":
            #   {"shot_01": {
            #      "task_id": None,
            #      "path": None,
            #      "error": "提交失败：ArkError"
            #     }
            #   }
            # } 更新子图的 video_results，而子图的这个 video_results 回头是会合并到父图的 video_results 字段里面的
            return shot_video_result(state, error=f"提交失败：{type(exc).__name__}")

    return submit


# 查询视频生成的情况，还是通过调用 VideoService 上面的 query 方法来查询
# 核心步骤：
# 1. 调用 VideoService 上面的 query 方法来查询，得到一个 response
# 2. 根据 response 的不同情况来更新子图的状态
def make_query_shot_video(service: VideoService, max_queries: int = 30):
    # 通过闭包的形式把 VideoService（视频生成服务）注入进来
    # 除了 VideoService，还有 max_queries（最大查询次数），设置了默认值为 30
    def query(state):
        try:
            # 从子图的状态拿到 task_id
            # 向方舟查一次视频生成情况
            response = service.query(state["task_id"])
        except (ArkError, OSError) as exc:
            return shot_video_result(state, error=f"查询失败：{type(exc).__name__}")

        # 这个 update 回头是用于更新子图状态的
        update = {"queries": state["queries"] + 1, "status": response.status}

        if (
            response.status == "succeeded"
            and response.content
            and response.content.video_url
        ):
            # 如果进入到此分支，说明视频生成成功
            return {**update, "video_url": response.content.video_url}
        if response.status not in ("queued", "running"):
            # 进入到这个分支，说明视频生成失败了
            error = getattr(response, "error", None)
            code = getattr(error, "code", None)
            return {
                **update,
                **shot_video_result(
                    state, error=f"查询结果：{response.status} {code or ''}".strip()
                ),
            }
        if update["queries"] >= max_queries:
            return {
                **update,
                **shot_video_result(state, error="达到查询次数上限，停止跟踪"),
            }

        # 如果上面都没有进入，说明视频还在生成中
        return update

    return query


# 需要等待
# 这里会涉及到一个中断
def wait_shot_video(state):
    # 中断，然后把如下信息（interrupt 里面的信息）传递出去，让用户看到
    interrupt(
        {
            "type": "video_wait",
            "shot_id": state["job"]["shot_id"],
            "task_id": state["task_id"],
            "status": state["status"],
            "queries": state["queries"],
        }
    )
    return {}  # 不更新子图的任何状态


def make_download_shot_video(service: VideoService):
    def download(state):
        job = state["job"]

        try:
            # path 拿到的就是生成的分镜视频，例如："outputs/videos/a1b2c3d4e5f6789012345678abcdef01/shot_01.mp4"
            path = service.download(state["video_url"], job["folder"], job["shot_id"])
        except OSError as exc:
            # 失败也要更新子图的 "video_results" 这个字段
            return shot_video_result(state, error=f"下载失败：{type(exc).__name__}")

        # 成功下载，也要更新子图的 "video_results" 字段
        return shot_video_result(state, path=path)

    return download
