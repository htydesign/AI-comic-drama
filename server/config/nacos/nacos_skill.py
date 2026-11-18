import os

import httpx
from opensandbox import Sandbox
from server.utils.sandbox import get_shared_sandbox
from server.config.nacos.nacos_access_token import get_access_token
from server.config.nacos_settings import nacos_settings

import asyncio

_SANDBOX_NACOS_ADDRESS = "http://host.docker.internal:8848"


async def _save_skill(
    *, skill_name: str, sandbox: Sandbox, zip_path: str, skill_dir: str
):

    access_token = await get_access_token()

    # 直传
    url = (
        f"{_SANDBOX_NACOS_ADDRESS}/nacos/v3/client/ai/skills"
        f"?namespaceId={nacos_settings.namespace_id}"
        f"&name={skill_name}&label=production"
    )

    result = await sandbox.commands.run(
        f"mkdir -p {os.path.dirname(zip_path)} {skill_dir} && "
        f'curl -fsS -H "accessToken: {access_token}" "{url}" -o {zip_path} && '
        f"unzip -o {zip_path} -d {skill_dir}"
    )

    # async with httpx.AsyncClient(
    #     base_url=nacos_settings.server_address,
    #     headers={"accessToken": access_token},
    # ) as client:
    #     response = await client.get(
    #         "/nacos/v3/client/ai/skills",
    #         params={
    #             "namespaceId": nacos_settings.namespace_id,
    #             "name": skill_name,
    #             "label": "production",
    #         },
    #     )

    # zip_bytes = response.content

    # await sandbox.files.write_file(path=zip_path, data=zip_bytes)

    # # 解压缩 unzip -o 压缩包地址 -d 解压地址
    # result = await sandbox.commands.run(
    #     command=f"mkdir -p {skill_dir} && " f"unzip -o {zip_path} -d {skill_dir}"
    # )

    if result.exit_code != 0:
        raise RuntimeError(f"解压技能 {skill_name} 失败: {result.error}")


async def save_skills(agent_name: str, skill_names: list[str] | None = None):
    """将指定的 skill 保存到指定的共享卷中"""
    if skill_names is None:
        skill_names = []

    sandbox = await get_shared_sandbox()
    skill_dir = f"/shared/skills/{agent_name}"
    await sandbox.commands.run(f"rm -rf {skill_dir}")
    await asyncio.gather(
        *[
            _save_skill(
                skill_name=skill_name,
                sandbox=sandbox,
                zip_path=f"/shared/skill_zips/{agent_name}/{skill_name}.zip",
                skill_dir=skill_dir,
            )
            for skill_name in skill_names
        ]
    )


if __name__ == "__main__":

    async def main():
        sandbox = await get_shared_sandbox()
        await _save_skill(
            skill_name="pptx",
            sandbox=sandbox,
            zip_path="/shared/skill_zips/main_agent/pptx.zip",
            skill_dir="/shared/skills/main_agent",
        )

    asyncio.run(main())
