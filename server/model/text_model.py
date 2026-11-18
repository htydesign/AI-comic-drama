from typing import Protocol

from server.model.ark_text_model import ArkTextModel
from server.schema.creative_requirement import CreativeRequirement
from server.schema.character_profile import CharacterProfile
from server.schema.quality import StoryboardQualityReport
from server.schema.scene_profile import SceneProfile
from server.schema.story_outline import StoryOutline
from server.schema.storyboard import StoryBoard


# 先规定“模型应该长什么样”
# Protocol 的核心作用就是：
# 告诉 Python 类型系统：TextModel 描述的是一种“结构要求”，
class TextModel(Protocol):
    def analyze_requirement(self, raw_requirement: str) -> CreativeRequirement | None:
        """把自然语言创意转换为经过校验的结构化需求。"""

    def generate_story_outline(
        self, requirement: CreativeRequirement
    ) -> StoryOutline | None:
        """先固定故事因果。"""

    def generate_characters(
        self, requirement: CreativeRequirement, outline: StoryOutline
    ) -> list[CharacterProfile] | None:
        """基于同一大纲生成角色设定。"""

    def generate_scenes(
        self, requirement: CreativeRequirement, outline: StoryOutline
    ) -> list[SceneProfile] | None:
        """基于同一大纲生成场景设定。"""

    def generate_storyboard(
        self,
        requirement: CreativeRequirement,
        outline: StoryOutline,
        characters: list[CharacterProfile],
        scenes: list[SceneProfile],
    ) -> list[StoryBoard] | None:
        """只引用已登记角色与场景，返回整版分镜。"""

    def evaluate_storyboard_quality(
        self,
        requirement: CreativeRequirement,
        outline: StoryOutline,
        characters: list[CharacterProfile],
        scenes: list[SceneProfile],
        storyboard: list[StoryBoard],
        previous_report: StoryboardQualityReport | None = None,
    ) -> StoryboardQualityReport | None:
        """评价当前分镜，不修改分镜。"""

    def revise_storyboard(
        self,
        requirement: CreativeRequirement,
        outline: StoryOutline,
        characters: list[CharacterProfile],
        scenes: list[SceneProfile],
        storyboard: list[StoryBoard],
        report: StoryboardQualityReport,
        revision_count: int = 0,
    ) -> list[StoryBoard] | None:
        """返回完整新版本，节点负责最终校验。"""
