from server.config.nacos.nacos_mcp import get_mcps
from server.config.nacos.nacos_schema import AgentSpec
from server.config.nacos_settings import nacos_settings
from server.config.nacos.nacos_access_token import get_access_token
from server.config.nacos.nacos_prompt import get_prompts
from server.config.nacos.nacos_skill import save_skills
import httpx
import asyncio
import json


async def get_agent_spec(agent_name: str) -> AgentSpec:
    access_token = await get_access_token()

    async with httpx.AsyncClient(
        base_url=nacos_settings.server_address, headers={"accessToken": access_token}
    ) as client:
        response = await client.get(
            "/nacos/v3/client/ai/agentspecs",
            params={
                "namespaceId": nacos_settings.namespace_id,
                "name": agent_name,
                "label": "production",
            },
        )
        response = response.json()

    if response["code"] != 0:
        return AgentSpec(name=agent_name)

    response = response["data"]
    config = response.get("content", {})
    config = json.loads(config)

    print("====", response)

    if "mcps" in config:
        config["mcps"] = await get_mcps(config["mcps"])
    system_prompt = (
        response.get("resource", {})
        .get(f"instruction_{agent_name}/AGENTS__MD", {})
        .get("content", "")
    )
    config["name"] = agent_name
    link_propmts = config.get("link_prompts", [])

    prompt = await get_prompts(link_propmts)

    config["system_prompt"] = system_prompt + "\n\n" + prompt

    skills = config.get("skills", [])
    await save_skills(agent_name, skills)

    return AgentSpec.model_validate(config)


if __name__ == "__main__":
    result = asyncio.run(get_agent_spec("main_agent"))
    print(result)
