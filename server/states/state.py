from typing import Annotated, NotRequired, TypedDict
import operator
from server.schema.character_profile import CharacterProfile
from server.schema.creative_requirement import CreativeRequirement
from server.schema.quality import ModelQualityReport, StoryboardQualityReport
from server.schema.revision_record import RevisionRecord
from server.schema.scene_profile import SceneProfile
from server.schema.story_outline import StoryOutline
from server.schema.storyboard import StoryBoard
from server.schema.storyboard_review import StoryboardReview
from server.schema.storyboard_validation import StoryboardValidation
from server.states.asset_reducer import merge_assets


class ComicDramaState(TypedDict):
    """整张图的状态"""

    # 原始需求
    raw_requirement: str

    requirement: NotRequired[CreativeRequirement]

    # 客户端和 Studio 用来判断走到哪一阶段。节点在业务写盘成功后才更新它。
    # 例：首次输入 "submitted"；分镜待审 "quality_passed"；成片待审 "final_video_ready"；验收通过 "final_video_approved"
    current_stage: str

    # 各节点只返回本节点新增的字符串。operator.add 追加到历史，避免后写覆盖先写。
    # 例：["已接收用户创意", "已生成结构化创意需求", "已生成故事大纲", "已收到人工审核命令：revise", "已按人工意见生成 v1 分镜"]
    events: Annotated[list[str], operator.add]

    # 故事大纲
    story_outline: NotRequired[StoryOutline]
    # 人物设定
    characters: NotRequired[list[CharacterProfile]]
    # 场景
    scenes: NotRequired[list[SceneProfile]]
    # 存储分镜列表
    storyboard: NotRequired[list[StoryBoard]]
    # 存储分镜的验证结果，是否通过了硬性坚持
    storyboard_validation: NotRequired[StoryboardValidation]

    # 评审分镜报告
    quality_report: NotRequired[StoryboardQualityReport | None]
    # 上一次的报告
    previous_quality_report: NotRequired[dict | None]
    # 记录修订的次数
    revision_count: NotRequired[int]
    # 本轮最多自动修订几次
    max_revisions: NotRequired[int]
    # 版本列表
    revision_history: NotRequired[list[RevisionRecord]]
    # 停止下一次修订的原因
    stop_reason: NotRequired[str | None]

    # 只累计模型修改的次数
    automatic_revision_count: NotRequired[int]
    # 只累计人工修改的次数
    human_revision_count: NotRequired[int]
    # 存储人工审核的决定
    review_result: NotRequired[StoryboardReview | None]
    # 人工审核时候，提交的内容有问题，报错信息会写入该字段。
    review_error: NotRequired[str | None]
    # 用户点通过时对应的内容版本
    approved_version: NotRequired[int | None]

    # 整个项目id
    project_id: NotRequired[str]
    # 视觉快照
    visual_bible: NotRequired[dict]
    # 视觉摘要
    visual_digest: NotRequired[str]
    # 素材索引
    assets: Annotated[dict[str, dict], merge_assets]
    # 最终生图报告
    reference_report: NotRequired[dict]
