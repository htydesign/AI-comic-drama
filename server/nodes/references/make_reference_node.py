from server.prompt.reference_prompts import (
    character_reference_request,
    scene_reference_request,
)
from server.schema.asset import Asset
from server.services.image.image_generator import ImageGenerationError, ImageGenerator
from server.states import ComicDramaState

from server.nodes.references.visual_bible import _checked_bible


def make_reference_node(generator: ImageGenerator, *, purpose: str):
    def generate_references(state: ComicDramaState) -> dict:
        bible = _checked_bible(state)
        if purpose == "character_reference":
            requests = [character_reference_request(bible, x) for x in bible.characters]
        else:
            requests = [scene_reference_request(bible, x) for x in bible.scenes]
        updates = {}
        for request in requests:
            common = {
                "purpose": request.purpose,
                "owner_id": request.owner_id,
                "version": request.version,
                "request_id": request.request_id,
                "prompt": request.prompt,
                "negative_prompt": request.negative_prompt,
                "size": request.size,
            }
            try:
                image = generator.generate(request)
            except ImageGenerationError as exc:
                asset = Asset(**common, status="failed", error_code=exc.code)
            except (OSError, ValueError):
                asset = Asset(
                    **common, status="failed", error_code="asset_storage_invalid"
                )
            else:
                asset = Asset(**common, status="succeeded", image=image)
            updates[request.request_id] = asset.model_dump(mode="json")
        return {
            "assets": updates,
            "events": [f"{purpose} 分支完成，共 {len(updates)} 项"],
        }

    return generate_references
