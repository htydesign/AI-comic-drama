import os

from .ark_text_model import ArkTextModel
from .fake_text_model import FakeTextModel
from .text_model import TextModel


def build_text_model() -> TextModel:
    provider = os.getenv("TEXT_MODEL_PROVIDER", "fake").strip().lower()

    if provider == "fake":

        planning_fault = os.getenv("FAKE_PLANNING_FAULT", "none").strip().lower()
        storyboard_fault = os.getenv("FAKE_STORYBOARD_FAULT", "none").strip().lower()
        quality_fault = os.getenv("FAKE_QUALITY_FAULT", "none").strip().lower()
        revision_scenario = os.getenv("FAKE_REVISION_SCENARIO", "none").strip().lower()

        if planning_fault not in {"none", "characters", "scenes"}:
            raise ValueError(f"不支持的 FAKE_PLANNING_FAULT：{planning_fault}")

        if storyboard_fault not in {
            "none",
            "duplicate_id",
            "unknown_character",
            "duration_mismatch",
        }:
            raise ValueError(f"不支持的 FAKE_STORYBOARD_FAULT：{storyboard_fault}")

        if quality_fault not in {
            "none",
            "plot_gap",
            "character_inconsistent",
            "visual_unclear",
            "motion_conflict",
            "invalid_report",
        }:
            raise ValueError(f"不支持的 FAKE_QUALITY_FAULT：{quality_fault}")

        if revision_scenario not in {
            "none",
            "second_pass",
            "always_fail",
            "unchanged",
            "hard_regression",
            "repeat_version",
        }:
            raise ValueError(f"不支持的 FAKE_REVISION_SCENARIO：{revision_scenario}")

        return FakeTextModel(
            planning_fault=planning_fault,
            storyboard_fault=storyboard_fault,
            quality_fault=quality_fault,
            revision_scenario=revision_scenario,
        )

    if provider == "ark":
        api_key = os.getenv("ARK_API_KEY", "").strip()
        model = os.getenv("ARK_MODEL", "").strip()

        if not api_key or not model:
            raise RuntimeError("使用 ark 时必须配置 ARK_API_KEY 和 ARK_MODEL")

        return ArkTextModel(api_key=api_key, model=model)  # type: ignore

    raise ValueError(f"不支持的 TEXT_MODEL_PROVIDER：{provider}")
