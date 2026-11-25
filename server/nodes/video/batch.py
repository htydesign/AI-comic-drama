"""派发批准的镜头，汇总后生成整部漫剧。"""

import shutil
from subprocess import CalledProcessError
from uuid import uuid4

from langgraph.graph import END
from langgraph.types import Send, interrupt

from server.schema.shot_frame_task import ShotFrameTask
from server.services.video.video_service import VideoService


def prepare_videos(state):
    decision = interrupt({"type": "video_start", "shots": len(state["frame_tasks"])})
    if decision != "start":
        return {"current_stage": "video_cancelled"}
    if shutil.which("ffmpeg") is None:
        return {"current_stage": "video_failed", "video_error": "找不到 FFmpeg"}
    folder = uuid4().hex
    jobs = []
    for raw in state["frame_tasks"]:
        task = ShotFrameTask.model_validate(raw)
        shot = task.shot
        frames = [
            state["approved_frames"][f"{shot.shot_id}:{kind}"]
            for kind in ("start", "end")
        ]
        jobs.append(
            {
                "shot_id": shot.shot_id,
                "order": shot.order,
                "folder": folder,
                "prompt": shot.video_prompt,
                "duration": shot.duration_seconds,
                "ratio": task.aspect_ratio,
                "frames": [
                    {k: frame[k] for k in ("local_path", "content_sha256")}
                    for frame in frames
                ],
            }
        )
    return {"current_stage": "generating_videos", "video_jobs": jobs}


def dispatch_videos(state):
    if state["current_stage"] != "generating_videos":
        return END
    return [Send("generate_video", {"job": job}) for job in state["video_jobs"]]


def make_compose_videos(service: VideoService):
    def compose_videos(state):
        jobs = sorted(state["video_jobs"], key=lambda job: job["order"])
        results = state.get("video_results", {})
        failed = [
            job["shot_id"]
            for job in jobs
            if not results.get(job["shot_id"], {}).get("path")
        ]
        if failed:
            return {
                "current_stage": "video_failed",
                "video_error": "分镜未完成：" + "、".join(failed),
            }
        try:
            path = service.compose(
                jobs[0]["folder"], [results[job["shot_id"]]["path"] for job in jobs]
            )
        except (CalledProcessError, OSError) as exc:
            return {
                "current_stage": "video_failed",
                "video_error": getattr(exc, "stderr", None) or str(exc),
            }
        return {"current_stage": "video_ready", "final_video_path": path}

    return compose_videos
