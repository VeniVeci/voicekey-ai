from __future__ import annotations

import base64
import ctypes
import json
import os
from ctypes import wintypes
from pathlib import Path

from .config import APP_DIR


SECRETS_PATH = APP_DIR / "secrets.json"
CRYPTPROTECT_UI_FORBIDDEN = 0x1


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _blob(data: bytes) -> tuple[DATA_BLOB, ctypes.Array]:
    buffer = ctypes.create_string_buffer(data)
    return DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def protect(value: str) -> str:
    if os.name != "nt":
        raise OSError("DPAPI is only available on Windows")
    source, keepalive = _blob(value.encode("utf-8"))
    result = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(source), "VoiceKeyAI", None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(result)
    ):
        raise ctypes.WinError()
    try:
        return base64.b64encode(ctypes.string_at(result.pbData, result.cbData)).decode("ascii")
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del keepalive


def unprotect(value: str) -> str:
    if os.name != "nt":
        raise OSError("DPAPI is only available on Windows")
    source, keepalive = _blob(base64.b64decode(value))
    result = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(source), None, None, None, None,
        CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(result)
    ):
        raise ctypes.WinError()
    try:
        return ctypes.string_at(result.pbData, result.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(result.pbData)
        del keepalive


class SecretStore:
    def __init__(self, path: Path = SECRETS_PATH):
        self.path = path

    def load(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            encrypted = json.loads(self.path.read_text(encoding="utf-8"))
            return {key: unprotect(value) for key, value in encrypted.items() if value}
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return {}

    def save(self, values: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        encrypted = {key: protect(value) for key, value in values.items() if value}
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(encrypted, indent=2), encoding="utf-8")
        temporary.replace(self.path)

