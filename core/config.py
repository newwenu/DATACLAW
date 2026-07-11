"""Claw 配置中心 — 统一管理所有运行时配置。

使用 pydantic-settings 从 .env 文件和环境变量加载配置，
提供类型安全、启动时校验、IDE 自动补全。

配置优先级: 环境变量 > .env 文件 > 默认值

原则: 只收录真正被代码消费的配置项，不预设"将来可能用到"的项。
"""

from __future__ import annotations

from pydantic import model_validator
from pydantic_settings import BaseSettings


class ClawConfig(BaseSettings):
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}

    main_model: str = "deepseek"

    llm_mode: str = "live"

    llm_proxy_url: str = "http://127.0.0.1:8000/v1"

    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-chat"

    dashscope_api_key: str = ""
    dashscope_base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    qwen_model: str = "qwen-plus"

    memory_extraction: bool = False
    memory_inject_long_term: bool = False
    memory_llm_cooldown: int = 30

    agent_temperature: float = 0.2

    tui_log_min_width: int = 80

    @model_validator(mode="after")
    def _normalize_main_model(self) -> ClawConfig:
        self.main_model = self.main_model.strip().lower()
        return self

    def validate_api_keys(self) -> list[str]:
        if self.llm_mode in ("mock", "proxy"):
            return []

        errors = []

        if self.main_model == "qwen":
            if not self.dashscope_api_key or self.dashscope_api_key.strip() in ("sk-", ""):
                errors.append("DASHSCOPE_API_KEY 未正确配置（不能为空或占位符 'sk-'）")
        else:
            if not self.deepseek_api_key or self.deepseek_api_key.strip() in ("sk-", ""):
                errors.append("DEEPSEEK_API_KEY 未正确配置（不能为空或占位符 'sk-'）")

        return errors


_config: ClawConfig | None = None


def get_config() -> ClawConfig:
    global _config
    if _config is None:
        _config = ClawConfig()
    return _config


def reload_config() -> ClawConfig:
    global _config
    _config = ClawConfig()
    return _config