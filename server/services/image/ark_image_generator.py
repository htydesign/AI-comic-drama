from __future__ import annotations

import base64
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from arkruntime import Ark
from arkruntime._exceptions import (
    ArkAPIConnectionError,
    ArkAPIStatusError,
    ArkAPITimeoutError,
    ArkAuthenticationError,
    ArkBadRequestError,
    ArkPermissionDeniedError,
    ArkRateLimitError,
)

from server.schema.generated_image import GeneratedImage
from server.schema.image_generation_request import ImageGenerationRequest
from server.storage.asset_storage import AssetStore

from server.services.image.image_generator import ImageGenerationError, prompt_digest


class ArkImageGenerator:
    """火山方舟适配器：它是项目中唯一认识 SDK 响应的地方。"""

    def __init__(
        self,
        store: AssetStore,
        *,
        api_key: str,
        model: str,
        timeout_seconds: float = 120.0,
        client: Ark | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("缺少 ARK_API_KEY")
        if not model:
            raise ValueError("缺少 ARK_IMAGE_MODEL")
        self.store = store
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = client or Ark.volc(api_key=api_key, max_retries=0)

    def generate(self, request: ImageGenerationRequest) -> GeneratedImage:

        for reference in request.reference_images:
            self.store.read_reference(reference)

        existing = self.store.load(request)
        if existing is not None:
            if existing.provider_model != self.model:
                raise ValueError("request_id 已属于其他模型，请使用新 ID")
            return existing

        try:
            provider_prompt = request.prompt
            if request.negative_prompt:
                provider_prompt += f"\n请避免：{request.negative_prompt}"
            # 在 SDK 边界临时编码参考图，云端不能读取本地文件路径。
            image_inputs = []
            for reference in request.reference_images:
                content = self.store.read_reference(reference)
                suffix = self.store._detect_suffix(content)
                mime = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".webp": "image/webp",
                }[suffix]
                encoded = base64.b64encode(content).decode("ascii")
                image_inputs.append(f"data:{mime};base64,{encoded}")
            extra = {"image": image_inputs} if image_inputs else {}

            response = self.client.images.generate(
                model=self.model,
                prompt=provider_prompt,
                size=request.size,
                response_format="url",
                watermark=False,
                sequential_image_generation="disabled",
                timeout=self.timeout_seconds,
                **extra,
            )

        except ArkAuthenticationError as exc:
            raise self._error("authentication_failed", exc, request) from exc
        except ArkPermissionDeniedError as exc:
            raise self._error("permission_denied", exc, request) from exc
        except ArkRateLimitError as exc:
            raise self._error("rate_limited", exc, request) from exc
        except ArkBadRequestError as exc:
            raise self._error("request_rejected", exc, request) from exc
        except ArkAPITimeoutError as exc:
            raise self._error("generation_timeout", exc, request) from exc
        except ArkAPIConnectionError as exc:
            raise self._error("provider_unavailable", exc, request) from exc
        except ArkAPIStatusError as exc:
            raise self._error("provider_error", exc, request) from exc

        data = getattr(response, "data", None)
        remote_url = getattr(data[0], "url", None) if data else None
        if not remote_url:
            raise ImageGenerationError(
                "invalid_response",
                "火山方舟未返回可下载的图片 URL",
                request_id=request.request_id,
            )
        content = self._download(remote_url, request)
        try:
            return self.store.save(
                request,
                content,
                provider_model=self.model,
                prompt_digest=prompt_digest(request),
                remote_url=remote_url,
            )
        except (OSError, ValueError) as exc:
            raise ImageGenerationError(
                "invalid_image_data",
                "图片内容或落盘结果无效",
                request_id=request.request_id,
            ) from exc

    def _download(self, remote_url: str, request: ImageGenerationRequest) -> bytes:
        parsed = urlparse(remote_url)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ImageGenerationError(
                "invalid_image_url",
                "平台返回的图片地址不是有效 HTTPS URL",
                request_id=request.request_id,
            )
        try:
            http_request = Request(
                remote_url, headers={"User-Agent": "ai-comic-drama/0.1"}
            )
            with urlopen(http_request, timeout=self.timeout_seconds) as response:
                # 限制单张图下载上限，避免异常响应占满内存。
                content = response.read(20 * 1024 * 1024 + 1)
        except OSError as exc:
            raise ImageGenerationError(
                "download_failed", "生成图片下载失败", request_id=request.request_id
            ) from exc
        if len(content) > 20 * 1024 * 1024:
            raise ImageGenerationError(
                "image_too_large",
                "生成图片超过 20 MiB 上限",
                request_id=request.request_id,
            )
        return content

    @staticmethod
    def _error(code: str, exc: Exception, request: ImageGenerationRequest):
        # 不把密钥、请求头或平台完整响应混入业务错误。
        messages = {
            "authentication_failed": "图像服务鉴权失败",
            "permission_denied": "没有目标图像模型的调用权限",
            "rate_limited": "图像服务限流",
            "request_rejected": "图像请求被平台拒绝，请检查参数与内容",
            "generation_timeout": "图像生成请求超时，平台结果未知",
            "provider_unavailable": "无法连接图像服务",
            "provider_error": "图像服务返回错误",
        }
        return ImageGenerationError(code, messages[code], request_id=request.request_id)
