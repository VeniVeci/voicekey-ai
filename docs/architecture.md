# 架构说明

```text
┌──────────────┐     ┌─────────────┐     ┌──────────────────┐
│ Hotkey Hook  │ ──▶ │ WAV Recorder│ ──▶ │ ASR              │
│ hotkey.py    │     │ audio.py    │     │ cloud / local    │
└──────────────┘     └─────────────┘     └────────┬─────────┘
                                                   │ raw text
                                                   ▼
┌──────────────┐     ┌─────────────┐     ┌──────────────────┐
│ Focused App  │ ◀── │ Clipboard + │ ◀── │ Optional LLM     │
│ text field   │     │ Ctrl+V      │     │ faithful polish  │
└──────────────┘     └─────────────┘     └──────────────────┘
```

## 模块边界

- `hotkey.py`：可配置的 Windows 低级键盘钩子，默认 `Alt + Q`。
- `audio.py`：单声道 16 kHz PCM 录音和临时 WAV 生命周期。
- `providers.py`：云端 multipart ASR、本地 faster-whisper、兼容 Chat Completions 的润色。
- `config.py`：非敏感 JSON 配置及默认的忠实校对提示词。
- `secrets.py`：使用当前用户作用域的 Windows DPAPI 加密 API Key。
- `injector.py`：通过剪贴板和 `Ctrl + V` 向当前焦点窗口交付文本。
- `app.py`：状态机、后台线程、设置页面和状态浮层。

## 状态机

```text
IDLE --hotkey--> RECORDING --hotkey--> PROCESSING --success/error--> IDLE
```

`PROCESSING` 期间重复按快捷键不会启动第二条任务。模型请求在后台线程执行，Tk 主线程只负责界面和剪贴板。

## 安全边界

- 密钥不进入普通配置、日志和 Git。
- 云端 ASR 仅获得本次 WAV；润色模型仅获得转写文本和用户主动配置的词库。
- 系统提示明确把口述内容视为数据，不把其中的命令当作模型指令。
- 临时音频在成功或异常后统一删除。
- 应用不保留历史正文；未来若加入历史功能，必须默认关闭并提供明确删除入口。
