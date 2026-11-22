from typing import Literal

from pydantic import BaseModel, ConfigDict

from .character_profile import CharacterProfile
from .image_reference import ImageReference
from .scene_profile import SceneProfile
from .storyboard import StoryBoard


class ShotFrameTask(BaseModel):
    """一张镜头任务单；不包含全部故事、所有镜头或客户端对象。"""

    model_config = ConfigDict(extra="forbid")
    project_id: str
    version: int
    visual_digest: str
    generation_profile: str
    visual_style: str
    palette: str
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    negative_prompt: str
    shot: StoryBoard
    characters: list[CharacterProfile]
    scene: SceneProfile
    reference_images: list[ImageReference]
