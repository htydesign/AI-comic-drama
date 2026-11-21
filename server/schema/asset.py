from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .generated_image import GeneratedImage


class Asset(BaseModel):
    """一项参考图资源：成功保存 GeneratedImage，失败保存结构化错误。"""

    model_config = ConfigDict(extra="forbid")
    purpose: Literal["character_reference", "scene_reference"]
    owner_id: str = Field(pattern=r"^(char|scene)_[a-z0-9_]+$")
    version: int = Field(ge=0)
    request_id: str = Field(pattern=r"^img_[a-z0-9_]+$")
    status: Literal["succeeded", "failed"]
    prompt: str
    negative_prompt: str
    size: str
    image: GeneratedImage | None = None
    error_code: str | None = None

    @model_validator(mode="after")
    def check_result(self):
        if self.status == "succeeded":
            if self.image is None or self.error_code is not None:
                raise ValueError("成功素材必须有 image，且不能有 error_code")
            if (
                self.image.request_id,
                self.image.purpose,
                self.image.owner_id,
                self.image.version,
                self.image.prompt,
                self.image.negative_prompt,
                self.image.size,
            ) != (
                self.request_id,
                self.purpose,
                self.owner_id,
                self.version,
                self.prompt,
                self.negative_prompt,
                self.size,
            ):
                raise ValueError("成功图片必须与素材请求完全对应")
        elif self.image is not None or not self.error_code:
            raise ValueError("失败素材必须有 error_code，且不能有成功 image")
        return self
