from typing import Literal

from pydantic import BaseModel
import yaml

from server.config.nacos.nacos_access_token import get_access_token
from server.config.nacos.nacos_schema import OpenSandboxConfig
from server.config.nacos_settings import nacos_settings

import asyncio
import httpx

from server.utils.func_tools import func_cache

type ConfigName = Literal["sandbox_config"]

_GROUPNAME = "ai_comic_drama"


@func_cache(ttl=nacos_settings.ttl, lazy=True)
async def _get_config_content(config_name: ConfigName) -> str | None:
    access_token = await get_access_token()

    async with httpx.AsyncClient(
        base_url=nacos_settings.server_address, headers={"accessToken": access_token}
    ) as client:
        response = await client.get(
            "/nacos/v3/client/cs/config",
            params={
                "namespaceId": nacos_settings.namespace_id,
                "groupName": _GROUPNAME,
                "dataId": config_name,
            },
        )

        response.raise_for_status()
        response = response.json()

    if response["code"] != 0:
        return None
    response = response["data"]["content"]

    return response


async def get_config[T: BaseModel](config_name: ConfigName, schema: type[T]) -> T:
    content = await _get_config_content(config_name)

    if content is None:
        return schema()

    dict = yaml.safe_load(content)

    return schema.model_validate(dict)


if __name__ == "__main__":
    config = asyncio.run(get_config("sandbox_config", OpenSandboxConfig))
    print(config)
