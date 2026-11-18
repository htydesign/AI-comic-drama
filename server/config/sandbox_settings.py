import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel

# 显式加载项目根目录的 .env，确保沙箱服务地址与密钥可复现。
# 说明：pydantic-settings 的 env_prefix 机制在当前环境下无法从 .env 读取值
# （domain/api_key 会得到空串，SDK 随后回退到默认的 localhost:8080，请求打错服务）。
# 因此改为 load_dotenv 灌入 os.environ 后显式读取。
load_dotenv(Path(__file__).resolve().parents[3] / ".env")


class SandboxSettings(BaseModel):
    domain: str = ""
    api_key: str = ""


sandbox_settings = SandboxSettings(
    domain=os.getenv("OPEN_SANDBOX_DOMAIN", ""),
    api_key=os.getenv("OPEN_SANDBOX_API_KEY", ""),
)
