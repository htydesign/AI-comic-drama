import hashlib

from server.schema.image_generation_request import ImageGenerationRequest
from server.schema.visual_bible import VisualBible
from server.schema.character_profile import CharacterProfile
from server.schema.scene_profile import SceneProfile


def visual_digest(bible: VisualBible) -> str:
    return hashlib.sha256(bible.model_dump_json().encode()).hexdigest()[:16]


def _request(bible: VisualBible, owner_id: str, purpose, prompt: str):
    # ID 同时编码作品、内容版本、视觉快照和平台配置，避免跨作品/模型复用。
    return ImageGenerationRequest(
        request_id=f"img_{bible.project_id}_{purpose}_{owner_id}_v{bible.version}_{visual_digest(bible)}",
        purpose=purpose,
        owner_id=owner_id,
        version=bible.version,
        prompt=prompt,
        negative_prompt=bible.negative_prompt,
        size=bible.reference_size,
    )


def character_reference_request(bible: VisualBible, character: CharacterProfile):
    return _request(
        bible,
        character.character_id,
        "character_reference",
        f"角色视觉参考图；统一画风：{bible.visual_style}；统一色彩：{bible.palette}。\n"
        f"角色：{character.name}；身份：{character.identity}；性格气质：{character.personality}。\n"
        f"稳定外观：{character.appearance}；固定服装：{character.clothing}。\n"
        f"辨识关键词：{'、'.join(character.visual_keywords)}。\n"
        "单一角色，全身站姿，简洁中性背景，清晰展示脸部、发型与服装；无文字标签。",
    )


def scene_reference_request(bible: VisualBible, scene: SceneProfile):
    return _request(
        bible,
        scene.scene_id,
        "scene_reference",
        f"场景视觉参考图；统一画风：{bible.visual_style}；统一色彩：{bible.palette}。\n"
        f"场景：{scene.name}；时间：{scene.time}；空间布局：{scene.location}。\n"
        f"光线：{scene.lighting}；场景主色：{scene.colors}。\n"
        f"环境关键词：{'、'.join(scene.visual_keywords)}。\n"
        "空镜头，无人物，不加入分镜动作，展示环境布局与固定元素；无文字标签。",
    )
