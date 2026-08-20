from pathlib import Path

import pytest

from voicekey.providers import (
    ProviderError,
    build_multipart,
    extract_response_text,
    normalize_model_text,
    validate_service_url,
)


def test_normalize_model_text():
    assert normalize_model_text('```text\n你好，世界。\n```') == "你好，世界。"
    assert normalize_model_text('“你好”') == "你好"


def test_multipart_contains_fields_and_file(tmp_path: Path):
    audio = tmp_path / "sample.wav"
    audio.write_bytes(b"RIFF-test")
    body, boundary = build_multipart({"model": "asr-test", "language": "zh"}, "file", audio)
    assert boundary.encode() in body
    assert b'asr-test' in body
    assert b'filename="sample.wav"' in body
    assert b"RIFF-test" in body


def test_extract_responses_api_text():
    response = {"output": [{"content": [{"type": "output_text", "text": "整理后的文字"}]}]}
    assert extract_response_text(response) == "整理后的文字"


def test_remote_http_is_blocked_by_default():
    with pytest.raises(ProviderError):
        validate_service_url("http://192.168.1.8/v1")
    validate_service_url("http://localhost:8000/v1")
    validate_service_url("https://example.com/v1")
