from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from server.schema.image_reference import ImageReference


class GeneratedImage(BaseModel):
    """已规范化的素材结果；State 不需要理解平台原始响应。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    asset_id: str = Field(pattern=r"^asset_img_[a-z0-9_]+$")
    request_id: str = Field(pattern=r"^img_[a-z0-9_]+$")
    purpose: Literal[
        "character_reference",
        "scene_reference",
        "shot_start",
        "shot_end",
    ]
    owner_id: str = Field(pattern=r"^(project|char|scene|shot)_[a-z0-9_]+$")
    version: int = Field(ge=0)
    status: Literal["succeeded"] = "succeeded"
    local_path: str = Field(min_length=1)
    remote_url: str | None = None
    provider_request_id: str | None = None
    provider_model: str
    prompt: str
    negative_prompt: str = ""
    size: str
    prompt_digest: str = Field(pattern=r"^[a-f0-9]{16}$")
    request_digest: str = Field(pattern=r"^[a-f0-9]{16}$")
    reused: bool = False
    reference_images: list[ImageReference] = Field(default_factory=list)
