import json
import logging
import re
from typing import Any
from langchain.chat_models import BaseChatModel


from server.config.nacos.nacos_agent_spec import get_agent_spec
from server.prompt.character_prompt import CHARACTER_PROMPT
from server.prompt.scene_prompt import SCENE_PROMPT
from server.prompt.story_prompt import STORY_PROMPT
from server.prompt.storyboard_prompt import STORYBOARD_PROMPT
from server.prompt.system_prompt import SYSTEM_PROMPT
from server.prompt.quality_prompt import QUALITY_PROMPT
from server.prompt.revision_prompt import REVISION_PROMPT

from server.schema.character_profile import CharacterProfile
from server.schema.character_list import CharacterList
from server.schema.creative_requirement import CreativeRequirement
from server.schema.scene_profile import SceneProfile
from server.schema.scene_list import SceneList
from server.schema.story_outline import StoryOutline
from server.schema.storyboard import StoryBoard
from server.schema.storyboard_list import StoryBoardList
from server.schema.quality import StoryboardQualityReport, ModelQualityReport
from server.utils.create_model import create_model

from server.config.nacos.nacos_prompt import get_prompt


def normalize_quality_report(
    report: ModelQualityReport, known_ids: list[str]
) -> StoryboardQualityReport:
    """精确 ID 优先；仅修正唯一的纯数字后缀格式差异，不按 order 猜测。"""
    known = set(known_ids)
    numeric_ids: dict[int, list[str]] = {}
    for shot_id in known:
        match = re.fullmatch(r"shot_([0-9]+)", shot_id)
        if match:
            numeric_ids.setdefault(int(match.group(1)), []).append(shot_id)

    issues = []
    corrections = []
    for issue in report.issues:
        original = issue.shot_id
        if original is None or original in known:
            issues.append(issue)
            continue
        match = re.fullmatch(r"shot_([0-9]+)", original)
        candidates = numeric_ids.get(int(match.group(1)), []) if match else []
        if len(candidates) != 1:
            raise ValueError(
                f"质量报告引用无法唯一匹配的分镜：{original}；"
                f"候选={sorted(candidates)}；合法 ID={sorted(known)}"
            )
        corrected = candidates[0]
        issues.append(issue.model_copy(update={"shot_id": corrected}))
        corrections.append((original, corrected))

    result = report.model_copy(update={"issues": issues}).to_report()
    for original, corrected in corrections:
        logging.getLogger(__name__).warning(
            "质量报告镜头 ID 格式纠正：%s → %s", original, corrected
        )
    return result


async def create_ark_client() -> BaseChatModel:
    agent_spec_config = await get_agent_spec("chat-standard")
    return create_model(agent_spec_config.model)


class ArkTextModel:
    """火山方舟结构化输出适配器"""

    def __init__(self, *, api_key: str, model_name: str) -> None:

        # self._client = Ark.volc(api_key=api_key)
        self._model_name = model_name
        # 客户端在首次调用时惰性创建：create_model() 内部依赖 get_config()
        # （LangGraph runnable context），且 store 绑定主事件循环，
        # 因此只能由 async 节点在主循环上 await 创建，不能在 __init__/同步桥接里做。
        self._client: BaseChatModel | None = None

    async def _ensure_client(self) -> None:
        if self._client is None:
            self._client = await create_ark_client()

    async def analyze_requirement(self, raw_requirement: str) -> CreativeRequirement:
        """把自然语言创意转换为经过校验的结构化需求。"""

        await self._ensure_client()
        assert self._client is not None

        _prompt = await get_prompt("system_prompt")

        client = self._client.with_structured_output(CreativeRequirement)

        result = await client.ainvoke(
            [
                {"role": "system", "content": _prompt},
                {"role": "user", "content": raw_requirement},
            ]
        )
        requirement = result

        # completion = self._client.beta.chat.completions.parse(
        #     model=self._model_name,
        #     messages=[
        #         {"role": "system", "content": SYSTEM_PROMPT},
        #         {"role": "user", "content": raw_requirement},
        #     ],
        #     response_format=CreativeRequirement,
        # )

        # requirement = completion.choices[0].message.parsed

        if requirement is None:
            raise ValueError("文本模型没有返回可解析的结构化数据")

        return requirement

    async def _parse(
        self,
        *,
        prompt_name: str | None = None,
        system_prompt: str | None = None,
        payload: dict[str, Any],
        schema: type[Any],
    ) -> Any:
        """三种策划调用共用第 04 篇验证过的结构化输出方式。"""
        await self._ensure_client()
        assert self._client is not None
        client = self._client.with_structured_output(schema)

        if prompt_name is None and system_prompt is not None:
            _prompt = system_prompt
        else:
            _prompt = await get_prompt(prompt_name)

        result = await client.ainvoke(
            [
                {"role": "system", "content": _prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ]
        )
        parsed = result

        # completion = self._client.beta.chat.completions.parse(
        #     model=self._model_name,
        #     messages=[
        #         {"role": "system", "content": system_prompt},
        #         {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        #     ],
        #     response_format=schema,
        # )
        # parsed = completion.choices[0].message.parsed
        if parsed is None:
            raise ValueError("文本模型没有返回可解析的策划结果")
        return parsed

    async def generate_story_outline(
        self, requirement: CreativeRequirement
    ) -> StoryOutline:
        return await self._parse(
            prompt_name="story_prompt",
            payload={"requirement": requirement.model_dump(mode="json")},
            schema=StoryOutline,
        )

    async def generate_characters(
        self, requirement: CreativeRequirement, outline: StoryOutline
    ) -> list[CharacterProfile]:
        result = await self._parse(
            prompt_name="character_prompt",
            payload={
                "requirement": requirement.model_dump(mode="json"),
                "story_outline": outline.model_dump(mode="json"),
            },
            schema=CharacterList,
        )
        return result.characters

    async def generate_scenes(
        self, requirement: CreativeRequirement, outline: StoryOutline
    ) -> list[SceneProfile]:
        result = await self._parse(
            prompt_name="scene_prompt",
            payload={
                "requirement": requirement.model_dump(mode="json"),
                "story_outline": outline.model_dump(mode="json"),
            },
            schema=SceneList,
        )
        return result.scenes

    async def generate_storyboard(
        self,
        requirement: CreativeRequirement,
        outline: StoryOutline,
        characters: list[CharacterProfile],
        scenes: list[SceneProfile],
    ) -> list[StoryBoard]:
        # 【重要】把目标数量、总时长、可用 ID 连同完整设定传给模型。
        # 结构化解析只校验单个字段；跨镜头规则仍由 Python 校验节点负责。
        result = await self._parse(
            prompt_name="storyboard_prompt",
            payload={
                "requirement": requirement.model_dump(mode="json"),
                "story_outline": outline.model_dump(mode="json"),
                "characters": [item.model_dump(mode="json") for item in characters],
                "scenes": [item.model_dump(mode="json") for item in scenes],
                "target_shot_count": requirement.shot_count,
                "target_duration_seconds": requirement.duration_seconds,
                "allowed_character_ids": [item.character_id for item in characters],
                "allowed_scene_ids": [item.scene_id for item in scenes],
            },
            schema=StoryBoardList,
        )
        return result.storyboard_list

    async def evaluate_storyboard_quality(
        self,
        requirement: CreativeRequirement,
        outline: StoryOutline,
        characters: list[CharacterProfile],
        scenes: list[SceneProfile],
        storyboard: list[StoryBoard],
        previous_report: StoryboardQualityReport | None = None,
    ) -> StoryboardQualityReport:
        known_ids = [shot.shot_id for shot in storyboard]
        # 每次取当前 State 的真实 ID，不硬编码五个镜头，也不把 order 当 ID。

        prompt = await get_prompt("quality_prompt")

        system = prompt + (
            "\n本次合法镜头 ID："
            + json.dumps(known_ids, ensure_ascii=False)
            + "。issues 中的 shot_id 必须逐字复制上述值，或使用 null 表示全局问题。"
            "ID 不是镜头序号，不得自行构造、删掉前导零或缩写。"
        )
        report = await self._parse(
            system_prompt=system
            + (
                "\n这是修订后的复评：先逐项核对 previous_quality_report 中的问题。"
                "summary 简述旧问题已解决/仍存在/无法确认，再检查整稿新增问题。"
                "已解决的问题不再列入 issues；未解决与新增问题须有当前稿证据，"
                "沿用相同严重程度判据。旧报告只是待核对依据，不是正确性证明；"
                "不得为证明修订有用而放行，也不得为找问题而捏造新问题。"
                if previous_report is not None
                else ""
            ),
            payload={
                "requirement": requirement.model_dump(mode="json"),
                "story_outline": outline.model_dump(mode="json"),
                "characters": [item.model_dump(mode="json") for item in characters],
                "scenes": [item.model_dump(mode="json") for item in scenes],
                "storyboard": [item.model_dump(mode="json") for item in storyboard],
                "previous_quality_report": (
                    previous_report.model_dump(mode="json")
                    if previous_report is not None
                    else None
                ),
            },
            schema=ModelQualityReport,
        )
        return normalize_quality_report(report, known_ids)

    async def revise_storyboard(
        self,
        requirement: CreativeRequirement,
        outline: StoryOutline,
        characters: list[CharacterProfile],
        scenes: list[SceneProfile],
        storyboard: list[StoryBoard],
        report: StoryboardQualityReport,
        revision_count: int = 0,
    ) -> list[StoryBoard]:
        old_by_id = {shot.shot_id: shot for shot in storyboard}

        if len(old_by_id) != len(storyboard):
            raise ValueError("真实局部修订要求原稿 shot_id 唯一，先处理硬规则错误")

        targets = set(report.affected_shot_ids) or set(old_by_id)
        unknown = targets - set(old_by_id)

        if unknown:
            raise ValueError(f"修订目标引用未知分镜：{sorted(unknown)}")

        allowed_ids = [shot.shot_id for shot in storyboard if shot.shot_id in targets]

        prompt = await get_prompt("revision_prompt")

        result = await self._parse(
            system_prompt=prompt
            + "\n本次唯一允许返回的镜头 ID："
            + json.dumps(allowed_ids, ensure_ascii=False),
            payload={
                "requirement": requirement.model_dump(mode="json"),
                "story_outline": outline.model_dump(mode="json"),
                "characters": [item.model_dump(mode="json") for item in characters],
                "scenes": [item.model_dump(mode="json") for item in scenes],
                "storyboard": [item.model_dump(mode="json") for item in storyboard],
                "quality_report": report.model_dump(mode="json"),
                "allowed_shot_ids": allowed_ids,
            },
            schema=StoryBoardList,
        )

        revised = [StoryBoard.model_validate(shot) for shot in result.storyboard_list]
        returned_ids = [shot.shot_id for shot in revised]

        if len(set(returned_ids)) != len(returned_ids) or set(returned_ids) != targets:
            raise ValueError("修订输出必须恰好覆盖允许的镜头 ID，不能遗漏、重复或越界")

        revised_by_id = {shot.shot_id: shot for shot in revised}

        if any(shot.order != old_by_id[shot.shot_id].order for shot in revised):
            raise ValueError("修订不得改变目标镜头 order")

        if sum(shot.duration_seconds for shot in revised) != sum(
            old_by_id[shot_id].duration_seconds for shot_id in targets
        ):
            raise ValueError("修订不得改变目标镜头时长合计")

        return [revised_by_id.get(shot.shot_id, shot) for shot in storyboard]
