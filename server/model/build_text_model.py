import os
from typing import Any

from server.utils.create_model import create_model
from .ark_text_model import ArkTextModel
from .fake_text_model import FakeTextModel
from .text_model import TextModel
from server.config.nacos.nacos_schema import AgentSpec
from server.config.nacos.nacos_agent_spec import get_agent_spec


class build_model:
    _agent_config: AgentSpec | None = None

    def _get_model(self) -> Any:
        if not self._agent_config:
            return create_model()
        return create_model(self._agent_config.model)

    async def _get_agent_config(self):
        if not self._agent_config:
            self._agent_config = await get_agent_spec("chat_agent")


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

        return ArkTextModel(api_key=api_key, model_name=model)

    raise ValueError(f"不支持的 TEXT_MODEL_PROVIDER：{provider}")
