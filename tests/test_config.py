import json

from voicekey.config import AppSettings, load_settings, save_settings
from voicekey.secrets import SecretStore


def test_settings_roundtrip(tmp_path):
    path = tmp_path / "config.json"
    settings = AppSettings(glossary="千问, Chroma")
    settings.asr.model = "custom-asr"
    settings.polish.enabled = False
    save_settings(settings, path)

    loaded = load_settings(path)
    assert loaded.glossary == "千问, Chroma"
    assert loaded.asr.model == "custom-asr"
    assert loaded.polish.enabled is False
    assert "api_key" not in json.loads(path.read_text(encoding="utf-8"))["asr"]


def test_invalid_config_falls_back(tmp_path):
    path = tmp_path / "config.json"
    path.write_text("not-json", encoding="utf-8")
    assert load_settings(path).sample_rate == 16000


def test_new_user_defaults_are_local_and_private():
    settings = AppSettings()
    assert settings.asr.backend == "local"
    assert settings.polish.enabled is False
    assert settings.polish.credential_source == "manual"
    assert settings.allow_insecure_http is False


def test_secret_store_uses_dpapi(tmp_path):
    store = SecretStore(tmp_path / "secrets.json")
    store.save({"asr_api_key": "secret-value"})
    assert "secret-value" not in store.path.read_text(encoding="utf-8")
    assert store.load()["asr_api_key"] == "secret-value"
