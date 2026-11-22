from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from server.schema.image_reference import ImageReference


class ImageGenerationRequest(BaseModel):
    """项目自己的图像生成请求，不暴露火山方舟 SDK 类型。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    request_id: str = Field(pattern=r"^img_[a-z0-9_]+$")
    purpose: Literal[
        "character_reference",
        "scene_reference",
        "shot_start",
        "shot_end",
    ]
    owner_id: str = Field(pattern=r"^(project|char|scene|shot)_[a-z0-9_]+$")
    version: int = Field(ge=0)
    prompt: str = Field(min_length=1, max_length=4000)
    negative_prompt: str = Field(default="", max_length=2000)
    size: str = Field(default="2048x2048", pattern=r"^(\d{3,4}x\d{3,4}|[124]K)$")
    # 角色/场景参考输入，不把 Base64 存入 State。
    reference_images: list[ImageReference] = Field(default_factory=list, max_length=8)
