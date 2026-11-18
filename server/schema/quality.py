from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing import Literal

type ErrorCodeList = Literal[
    "hard_rule",
    "plot_gap",
    "character_inconsistent",
    "visual_unclear",
    "motion_conflict",
]


class QualityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    code: ErrorCodeList
    severity: Literal["error", "warning"]
    shot_id: str | None = Field(default=None, pattern=r"^shot_[a-z0-9_]+$")
    description: str = Field(min_length=1)
    suggestion: str = Field(min_length=1)


class StoryboardQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    is_passed: bool
    summary: str = Field(min_length=1)
    issues: list[QualityIssue]
    affected_shot_ids: list[str]

    @model_validator(mode="after")
    def check_consistency(self):
        blocking = any(issue.severity == "error" for issue in self.issues)
        if self.is_passed == blocking:
            raise ValueError("is_passed 必须与 error 级问题一致")
        expected = {issue.shot_id for issue in self.issues if issue.shot_id}
        if set(self.affected_shot_ids) != expected or len(
            self.affected_shot_ids
        ) != len(expected):
            raise ValueError("affected_shot_ids 必须与问题中的 shot_id 一致且不重复")
        return self


class ModelQualityReport(BaseModel):
    """模型只生成问题事实，正式通过判断由 Python 推导。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    summary: str = Field(min_length=1)
    issues: list[QualityIssue]

    def to_report(self) -> StoryboardQualityReport:
        return StoryboardQualityReport(
            is_passed=not any(i.severity == "error" for i in self.issues),
            summary=self.summary,
            issues=self.issues,
            affected_shot_ids=sorted({i.shot_id for i in self.issues if i.shot_id}),
        )
