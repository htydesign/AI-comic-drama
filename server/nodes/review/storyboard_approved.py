from server.states import ComicDramaState


def storyboard_approved(state: ComicDramaState) -> dict[str, object]:
    return {
        "approved_version": state["revision_count"],
        "current_stage": "storyboard_approved",
        "stop_reason": None,
        "events": [f"人工已批准 v{state['revision_count']} 分镜"],
    }
