from __future__ import annotations

import math
import os
from dataclasses import dataclass
from pathlib import Path

from server.storage.asset_storage import AssetStore

from server.services.image.ark_image_generator import ArkImageGenerator
from server.services.image.fake_image_generator import FakeImageGenerator
from server.services.image.image_generator import ImageGenerator


@dataclass(frozen=True)
class ImageRuntimeConfig:
    """这次出图的运行配置。读出来之后字段不能再改。"""

    provider: str
    model: str
    timeout_seconds: float
    project_root: Path

    @classmethod
    def from_env(cls) -> ImageRuntimeConfig:
        return cls(
            provider=os.getenv("IMAGE_MODEL_PROVIDER", "fake").strip().lower(),
            model=os.getenv("ARK_IMAGE_MODEL", "").strip(),
            timeout_seconds=float(os.getenv("IMAGE_TIMEOUT_SECONDS", "120")),
            project_root=Path(__file__).resolve().parents[3],
        )


def build_image_generator_from_env() -> ImageGenerator:
    config = ImageRuntimeConfig.from_env()
    if not math.isfinite(config.timeout_seconds) or config.timeout_seconds <= 0:
        raise ValueError("IMAGE_TIMEOUT_SECONDS 必须是有限正数")
    store = AssetStore(project_root=config.project_root)
    if config.provider == "fake":
        owners = os.getenv("FAKE_IMAGE_FAIL_OWNER_IDS", "").strip()
        purposes = os.getenv("FAKE_IMAGE_FAIL_PURPOSES", "").strip()
        return FakeImageGenerator(
            store,
            failure=os.getenv("FAKE_IMAGE_FAILURE", "none").strip().lower(),
            fail_owner_ids=(
                frozenset(x.strip() for x in owners.split(",") if x.strip())
                if owners
                else None
            ),
            fail_purposes=(
                frozenset(x.strip() for x in purposes.split(",") if x.strip())
                if purposes
                else None
            ),
        )
    if config.provider == "ark":
        return ArkImageGenerator(
            store,
            api_key=os.getenv("ARK_API_KEY", ""),
            model=config.model,
            timeout_seconds=config.timeout_seconds,
        )
    raise ValueError("IMAGE_MODEL_PROVIDER 只能是 fake 或 ark")
