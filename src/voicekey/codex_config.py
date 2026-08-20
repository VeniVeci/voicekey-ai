from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ImportError:  # Python 3.10
    import tomli as tomllib


class CodexConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class CodexConnection:
    base_url: str
    api_key: str
    wire_api: str
    provider_name: str


def codex_home() -> Path:
    return Path(os.getenv("CODEX_HOME", Path.home() / ".codex"))


def load_codex_connection(home: Path | None = None) -> CodexConnection:
    root = home or codex_home()
    config_path = root / "config.toml"
    auth_path = root / "auth.json"
    if not config_path.exists():
        raise CodexConfigError(f"找不到 Codex 配置：{config_path}")
    try:
        config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        provider_id = config.get("model_provider", "openai")
        provider = config.get("model_providers", {}).get(provider_id, {})
        base_url = provider.get("base_url", "https://api.openai.com/v1")
        env_key = provider.get("env_key", "OPENAI_API_KEY")
        wire_api = provider.get("wire_api", "responses")
        provider_name = provider.get("name", provider_id)
    except (OSError, ValueError, TypeError) as error:
        raise CodexConfigError(f"无法读取 Codex 配置：{error}") from error

    api_key = os.getenv(env_key, "")
    if not api_key and auth_path.exists():
        try:
            auth = json.loads(auth_path.read_text(encoding="utf-8"))
            api_key = auth.get(env_key, "")
        except (OSError, ValueError, TypeError, json.JSONDecodeError) as error:
            raise CodexConfigError(f"无法读取 Codex 凭据：{error}") from error
    if not api_key:
        raise CodexConfigError(f"Codex 配置要求凭据 {env_key}，但环境变量和 auth.json 中均未找到")
    if wire_api not in {"responses", "chat_completions"}:
        raise CodexConfigError(f"暂不支持 Codex wire_api：{wire_api}")
    return CodexConnection(base_url, api_key, wire_api, provider_name)

