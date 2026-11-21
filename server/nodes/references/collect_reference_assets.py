from server.prompt.reference_prompts import (
    character_reference_request,
    scene_reference_request,
)
from server.schema.asset import Asset
from server.states import ComicDramaState

from server.nodes.references.visual_bible import _checked_bible


def collect_reference_assets(state: ComicDramaState) -> dict:
    bible = _checked_bible(state)
    requests = [character_reference_request(bible, x) for x in bible.characters]
    requests += [scene_reference_request(bible, x) for x in bible.scenes]
    succeeded, failed = [], []
    for request in requests:
        payload = state.get("assets", {}).get(request.request_id)
        asset = Asset.model_validate(payload) if payload else None
        matches = asset is not None and (
            asset.request_id,
            asset.purpose,
            asset.owner_id,
            asset.version,
            asset.prompt,
            asset.negative_prompt,
            asset.size,
        ) == (
            request.request_id,
            request.purpose,
            request.owner_id,
            request.version,
            request.prompt,
            request.negative_prompt,
            request.size,
        )
        if matches and asset.status == "succeeded":
            succeeded.append(request.request_id)
        else:
            failed.append(
                {
                    "request_id": request.request_id,
                    "owner_id": request.owner_id,
                    "purpose": request.purpose,
                    "error_code": (
                        (asset.error_code if matches else "asset_request_mismatch")
                        if asset
                        else "missing_asset"
                    ),
                }
            )
    return {
        "reference_report": {
            "version": bible.version,
            "visual_digest": state["visual_digest"],
            "expected_count": len(requests),
            "succeeded_ids": succeeded,
            "failed": failed,
            "is_complete": not failed,
        },
        "current_stage": (
            "reference_assets_failed" if failed else "reference_assets_ready"
        ),
        "events": [f"参考素材汇总：成功 {len(succeeded)}，失败 {len(failed)}"],
    }
