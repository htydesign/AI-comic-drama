from server.schema.asset import Asset


def merge_assets(current: dict, update: dict) -> dict:
    merged = dict(current)
    for key, payload in update.items():
        asset = Asset.model_validate(payload)
        if key != asset.request_id:
            raise ValueError("素材索引键必须等于 request_id")
        if key in merged:
            previous = Asset.model_validate(merged[key])
            identity = (
                "purpose",
                "owner_id",
                "version",
                "prompt",
                "negative_prompt",
                "size",
            )
            if any(
                getattr(previous, name) != getattr(asset, name) for name in identity
            ):
                raise ValueError("同一素材键出现不同请求")
        merged[key] = asset.model_dump(mode="json")
    return merged
