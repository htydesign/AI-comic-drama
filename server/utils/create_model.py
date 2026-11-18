from langchain.chat_models import BaseChatModel, init_chat_model
from server.utils.shared import get_thread_id
from server.config.nacos.nacos_schema import AgentModelConfig
from server.config.openai_settings import openai_settings


def create_model(model_config: AgentModelConfig | None = None) -> BaseChatModel:

    if model_config is None:
        model_config = AgentModelConfig()

    config = {
        "model": model_config.name,
        "model_provider": "openai_reasoning",
        "extra_body": {"enable_thinking": model_config.thinking},
    }

    if model_config.temperature is not None:
        config["temperature"] = model_config.temperature
    if model_config.top_p is not None:
        config["top_p"] = model_config.top_p

    thread_id = get_thread_id()

    if thread_id:
        config["default_headers"] = {"x-litellm-session-id": thread_id}

    model = init_chat_model(**config)
    return model
