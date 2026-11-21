from server.prompt.reference_prompts import visual_digest
from server.states import ComicDramaState

from server.nodes.references.visual_bible import _bible


def make_prepare_visual_bible(generation_profile: str):
    def prepare_visual_bible(state: ComicDramaState) -> dict:
        if state["current_stage"] != "storyboard_approved":
            raise ValueError("只有分镜审核通过后才能准备参考素材")
        bible = _bible(state, generation_profile)
        digest = visual_digest(bible)
        if state.get("visual_bible") is not None and (
            state["visual_bible"] != bible.model_dump(mode="json")
            or state.get("visual_digest") != digest
        ):
            raise ValueError("冻结视觉设定已变化，请检查上游，不能静默重用旧素材")
        return {
            "visual_bible": bible.model_dump(mode="json"),
            "visual_digest": digest,
            "current_stage": "reference_assets_generating",
            "events": ["已冻结审核版视觉设定"],
        }

    return prepare_visual_bible
