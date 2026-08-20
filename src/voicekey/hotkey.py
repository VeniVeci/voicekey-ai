from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes
from typing import Callable


WH_KEYBOARD_LL = 13
WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_SYSKEYDOWN = 0x0104
WM_SYSKEYUP = 0x0105
WM_QUIT = 0x0012
LLKHF_INJECTED = 0x10

VK_MODIFIERS = {
    0xA2: "ctrl", 0xA3: "ctrl", 0xA4: "alt", 0xA5: "alt",
    0xA0: "shift", 0xA1: "shift", 0x5B: "win", 0x5C: "win",
}
MODIFIER_ALIASES = {
    "control": "ctrl", "ctrl": "ctrl", "option": "alt", "alt": "alt",
    "shift": "shift", "windows": "win", "super": "win", "win": "win",
}
NAMED_KEYS = {"space": 0x20, "enter": 0x0D, "tab": 0x09, "escape": 0x1B, "esc": 0x1B}
DISPLAY_NAMES = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "win": "Win"}
MODIFIER_ORDER = ("ctrl", "alt", "shift", "win")


class HotkeyError(ValueError):
    pass


def parse_hotkey(value: str) -> tuple[frozenset[str], int, str]:
    parts = [part.strip().lower() for part in value.split("+") if part.strip()]
    if len(parts) < 2:
        raise HotkeyError("快捷键必须包含至少一个修饰键，例如 Alt+Q")
    modifiers: set[str] = set()
    key_name = ""
    key_code = 0
    for part in parts:
        modifier = MODIFIER_ALIASES.get(part)
        if modifier:
            modifiers.add(modifier)
            continue
        if key_name:
            raise HotkeyError("快捷键只能包含一个普通按键")
        if len(part) == 1 and part.isascii() and part.isalnum():
            key_name = part.upper()
            key_code = ord(key_name)
        elif part in NAMED_KEYS:
            key_name = "Esc" if part in {"escape", "esc"} else part.title()
            key_code = NAMED_KEYS[part]
        elif part.startswith("f") and part[1:].isdigit() and 1 <= int(part[1:]) <= 12:
            number = int(part[1:])
            key_name = f"F{number}"
            key_code = 0x6F + number
        else:
            raise HotkeyError(f"不支持的按键：{part}")
    if not modifiers or not key_code:
        raise HotkeyError("快捷键需要修饰键和一个普通按键")
    display = "+".join([DISPLAY_NAMES[item] for item in MODIFIER_ORDER if item in modifiers] + [key_name])
    return frozenset(modifiers), key_code, display


def normalize_hotkey(value: str) -> str:
    return parse_hotkey(value)[2]


class KBDLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("vkCode", wintypes.DWORD), ("scanCode", wintypes.DWORD),
        ("flags", wintypes.DWORD), ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


HOOKPROC = ctypes.WINFUNCTYPE(ctypes.c_longlong, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class GlobalHotkey:
    """Configurable low-level Windows hotkey hook."""

    def __init__(self, shortcut: str, callback: Callable[[], None]):
        if os.name != "nt":
            raise OSError("VoiceKey AI hotkey is Windows-only")
        self.modifiers, self.key_code, self.shortcut = parse_hotkey(shortcut)
        self.callback = callback
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._hook = None
        self._proc = None
        self._pressed_modifiers: set[str] = set()
        self._combo_active = False
        self.error: OSError | None = None
        self.ready = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, name="voicekey-hotkey", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(timeout=2)

    def _run(self) -> None:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        user32.SetWindowsHookExW.argtypes = [ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD]
        user32.SetWindowsHookExW.restype = wintypes.HHOOK
        user32.CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM]
        user32.CallNextHookEx.restype = ctypes.c_longlong
        user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        user32.UnhookWindowsHookEx.restype = wintypes.BOOL
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HMODULE
        self._thread_id = kernel32.GetCurrentThreadId()

        @HOOKPROC
        def proc(code, message, data):
            if code >= 0:
                event = ctypes.cast(data, ctypes.POINTER(KBDLLHOOKSTRUCT)).contents
                if not event.flags & LLKHF_INJECTED:
                    down = message in (WM_KEYDOWN, WM_SYSKEYDOWN)
                    up = message in (WM_KEYUP, WM_SYSKEYUP)
                    modifier = VK_MODIFIERS.get(event.vkCode)
                    if modifier:
                        if down:
                            self._pressed_modifiers.add(modifier)
                        elif up:
                            self._pressed_modifiers.discard(modifier)
                    elif event.vkCode == self.key_code:
                        if down and self.modifiers.issubset(self._pressed_modifiers):
                            if not self._combo_active:
                                self._combo_active = True
                                self.callback()
                            return 1
                        if up and self._combo_active:
                            self._combo_active = False
                            return 1
            return user32.CallNextHookEx(self._hook, code, message, data)

        self._proc = proc
        ctypes.set_last_error(0)
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, proc, module, 0)
        if not self._hook:
            self.error = ctypes.WinError(ctypes.get_last_error())
            self.ready.set()
            return
        self.ready.set()
        message = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(message))
            user32.DispatchMessageW(ctypes.byref(message))
        user32.UnhookWindowsHookEx(self._hook)
        self._hook = None
