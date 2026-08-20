import pytest

from voicekey.hotkey import HotkeyError, normalize_hotkey, parse_hotkey


@pytest.mark.parametrize(
    ("raw", "normalized"),
    [
        ("alt+q", "Alt+Q"),
        ("shift + ctrl + space", "Ctrl+Shift+Space"),
        ("win+f8", "Win+F8"),
    ],
)
def test_normalize_hotkey(raw, normalized):
    assert normalize_hotkey(raw) == normalized


def test_hotkey_requires_modifier():
    with pytest.raises(HotkeyError):
        parse_hotkey("Q")
