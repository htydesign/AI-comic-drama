from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .character_profile import CharacterProfile
from .scene_profile import SceneProfile


class VisualBible(BaseModel):
    """审核后的视觉快照；保存基础类型，方便服务检查点序列化。"""

    model_config = ConfigDict(extra="forbid", frozen=True)
    project_id: str = Field(pattern=r"^project_[a-z0-9_]+$")
    version: int = Field(ge=0)
    visual_style: str
    palette: str
    aspect_ratio: Literal["9:16", "16:9", "1:1"]
    reference_size: str = "2048x2048"
    negative_prompt: str
    characters: tuple[CharacterProfile, ...]
    scenes: tuple[SceneProfile, ...]
    generation_profile: str
