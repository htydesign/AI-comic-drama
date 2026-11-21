"""构建并校验参考素材共用的视觉快照。"""

import hashlib

from server.prompt.reference_prompts import visual_digest
from server.schema import (
    CharacterProfile,
    CreativeRequirement,
    SceneProfile,
    StoryBoard,
)
from server.schema.visual_bible import VisualBible
from server.states import ComicDramaState


def _bible(state: ComicDramaState, generation_profile: str) -> VisualBible:
    version = state.get("approved_version")
    if version is None or version != state.get("revision_count"):
        raise ValueError("批准版本与当前分镜版本不一致")
    requirement = CreativeRequirement.model_validate(state["requirement"])
    characters = tuple(CharacterProfile.model_validate(x) for x in state["characters"])
    scenes = tuple(SceneProfile.model_validate(x) for x in state["scenes"])
    char_ids = {x.character_id for x in characters}
    scene_ids = {x.scene_id for x in scenes}
    if (
        not characters
        or not scenes
        or len(char_ids) != len(characters)
        or len(scene_ids) != len(scenes)
    ):
        raise ValueError("角色和场景不能为空，ID 也不能重复")
    shots = [StoryBoard.model_validate(x) for x in state["storyboard"]]
    if not shots or any(
        x.scene_id not in scene_ids or not set(x.character_ids) <= char_ids
        for x in shots
    ):
        raise ValueError("分镜缺失或引用了未登记的角色/场景")
    default_id = (
        "project_" + hashlib.sha256(requirement.core_idea.encode()).hexdigest()[:12]
    )
    return VisualBible(
        project_id=state.get("project_id", default_id),
        version=version,
        visual_style=requirement.visual_style,
        palette="统一低饱和暖色基础，环境局部颜色服从已登记场景",
        aspect_ratio=requirement.aspect_ratio,
        negative_prompt="文字标签、水印、额外人物、角色外观与固定服装漂移",
        characters=characters,
        scenes=scenes,
        generation_profile=generation_profile,
    )


def _checked_bible(state: ComicDramaState) -> VisualBible:
    if state["current_stage"] != "reference_assets_generating":
        raise ValueError("参考素材节点只能读取已准备好的生成阶段")
    bible = VisualBible.model_validate(state["visual_bible"])
    if (
        bible != _bible(state, bible.generation_profile)
        or visual_digest(bible) != state["visual_digest"]
    ):
        raise ValueError("审核设定与视觉快照不一致")
    return bible
