from pydantic import BaseModel, ConfigDict, Field

from .quality import ErrorCodeList


class RevisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: int = Field(ge=0)
    fingerprint: str = Field(min_length=16, max_length=16)
    source_codes: list[ErrorCodeList] = Field(default_factory=list)
    target_shot_ids: list[str]
