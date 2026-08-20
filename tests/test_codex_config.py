import json

from voicekey.codex_config import load_codex_connection


def test_load_codex_connection(tmp_path, monkeypatch):
    (tmp_path / "config.toml").write_text(
        'model_provider = "gateway"\n[model_providers.gateway]\nname = "Gateway"\nbase_url = "http://127.0.0.1/v1"\nenv_key = "TEST_VOICE_KEY"\nwire_api = "responses"\n',
        encoding="utf-8",
    )
    (tmp_path / "auth.json").write_text(json.dumps({"TEST_VOICE_KEY": "secret"}), encoding="utf-8")
    monkeypatch.delenv("TEST_VOICE_KEY", raising=False)
    result = load_codex_connection(tmp_path)
    assert result.base_url == "http://127.0.0.1/v1"
    assert result.api_key == "secret"
    assert result.wire_api == "responses"
