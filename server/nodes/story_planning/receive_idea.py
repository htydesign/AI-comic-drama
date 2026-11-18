from server.states.state import ComicDramaState


def receive_idea(state: ComicDramaState) -> dict[str, object]:
    """接收用户创意，生成结构化创意需求"""

    raw_requirement = state["raw_requirement"].strip()

    if not raw_requirement:
        raise ValueError("raw_requirement 不能为空，请提供用户创意。")

    return {
        "raw_requirement": raw_requirement,
        "current_stage": "idea_received",
        "events": ["已接收用户创意"],
    }
