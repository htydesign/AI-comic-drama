"""方舟视频任务与本地 MP4。"""

import base64
import os
import shutil
import subprocess
from pathlib import Path
from urllib.request import urlopen

from arkruntime import Ark

from server.schema.image_reference import ImageReference
from server.storage.asset_storage import AssetStore


class VideoService:
    def __init__(self, store: AssetStore):
        self.store = store

    def submit(self, job: dict) -> str:
        content = [{"type": "text", "text": job["prompt"]}]
        for role, frame in zip(("first_frame", "last_frame"), job["frames"]):
            image = self.store.read_reference(ImageReference.model_validate(frame))
            mime = (
                "png"
                if image.startswith(b"\x89PNG")
                else ("jpeg" if image.startswith(b"\xff\xd8\xff") else "webp")
            )
            content.append(
                {
                    "type": "image_url",
                    "role": role,
                    "image_url": {
                        "url": f"data:image/{mime};base64,{base64.b64encode(image).decode()}"
                    },
                }
            )
        with self._client() as client:
            task = client.content_generation.tasks.create(
                model=os.environ["ARK_VIDEO_MODEL"],
                content=content,
                ratio=job["ratio"],
                duration=job["duration"],
                resolution=os.getenv("VIDEO_RESOLUTION", "720p"),
                generate_audio=False,
            )
        return task.id

    def query(self, task_id: str):
        with self._client() as client:
            return client.content_generation.tasks.get(task_id)

    @staticmethod
    def _client():
        return Ark.volc(api_key=os.environ["ARK_API_KEY"], timeout=60, max_retries=0)

    def download(self, url: str, folder: str, shot_id: str) -> str:
        directory = self.store.output_root / "videos" / folder
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{shot_id}.mp4"
        partial = path.with_suffix(".part")
        try:
            with urlopen(url, timeout=60) as response, partial.open("wb") as file:
                shutil.copyfileobj(response, file)
            partial.replace(path)
        finally:
            partial.unlink(missing_ok=True)
        return path.relative_to(self.store.project_root).as_posix()

    def compose(self, folder: str, paths: list[str]) -> str:
        directory = self.store.output_root / "videos" / folder
        manifest = directory / "concat.txt"
        manifest.write_text("".join(f"file '{Path(path).name}'\n" for path in paths))
        subprocess.run(
            [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "1",
                "-i",
                manifest.name,
                "-c",
                "copy",
                "final.part.mp4",
            ],
            cwd=directory,
            check=True,
            capture_output=True,
            text=True,
        )
        final = directory / "final.mp4"
        (directory / "final.part.mp4").replace(final)
        return final.relative_to(self.store.project_root).as_posix()
