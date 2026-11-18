import httpx
import asyncio
from server.config.nacos.nacos_schema import MCPServerConfig
from server.config.nacos.nacos_access_token import get_access_token
from server.config.nacos_settings import nacos_settings
from server.utils.func_tools import func_cache


@func_cache(
    ttl=nacos_settings.ttl,
    lazy=True,
)
async def get_mcp_config(mcp_name: str) -> MCPServerConfig | None:
    access_token = await get_access_token()
    async with httpx.AsyncClient(
        base_url=nacos_settings.server_address,
        timeout=10,
        headers={"accessToken": access_token},
    ) as client:
        response = await client.get(
            "/nacos/v3/admin/ai/mcp",
            params={"namespaceId": nacos_settings.namespace_id, "mcpName": mcp_name},
        )
        response = response.json()

        if response["code"] != 0:
            return None

    result = response["data"]

    endpoints = result.get("backendEndpoints", [])

    if len(endpoints) == 0:
        return None

    backend = endpoints[0]
    url = f"{backend["protocol"]}://{backend["address"]}:{backend["port"]}{backend["path"]}"

    tools_meta = result.get("toolSpec", {}).get("toolsMeta", {})

    disabled_tools = [
        name for name, value in tools_meta.items() if not value.get("enabled", True)
    ]

    return MCPServerConfig.model_validate(
        {"url": url, "disabled_tools": disabled_tools, "name": mcp_name}
    )


async def get_mcps(mcp_names: list[str]) -> dict[str, MCPServerConfig]:
    tasks = [get_mcp_config(mcp_name) for mcp_name in mcp_names]
    mcp_config = await asyncio.gather(*tasks)

    return {config.name: config for config in mcp_config if config is not None}


if __name__ == "__main__":
    result = asyncio.run(get_mcps(["langchain-docs"]))
    print(result)
