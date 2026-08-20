# VoiceKey AI（声键 AI）

一个面向 Windows 10/11 的开源 AI 语音输入工具。按下全局快捷键说话，再按一次结束，文字会自动输入到当前光标位置。

VoiceKey AI 将“听清楚”和“写得更清楚”拆成两个独立阶段：本地 `faster-whisper` 负责语音识别，可选的大模型负责忠实校对。新用户默认采用完全本地模式，不上传录音或转写文本。

```text
全局快捷键 → 麦克风录音 → 本地/云端 ASR → 可选 LLM 校对 → 当前光标
```

> 当前版本：`0.3.0 MVP`。适合体验和参与开发，尚无代码签名、安装器与自动更新。

## 功能

- 可配置全局快捷键，默认 `Alt + Q`，保存后立即生效。
- 本地 `faster-whisper`：默认使用 `small` 模型，音频无需离开电脑。
- 可选 OpenAI 兼容云端 ASR：支持 `/audio/transcriptions`。
- 可选 LLM 校对：支持 Responses API 和 Chat Completions。
- 可选读取本机 Codex provider；必须由用户主动启用。
- 个人词库：帮助修正项目名、人名和中英文专业术语。
- 显示 ASR 与 LLM 分阶段耗时。
- 自动粘贴到当前光标，并尽可能恢复原纯文本剪贴板。
- 手动填写的 API Key 使用 Windows DPAPI 加密。
- 无遥测，不保存转写历史。

## 安装运行

需要 Windows 10/11、Python 3.10 或更高版本。

```powershell
git clone https://github.com/VeniVeci/voicekey-ai.git
cd voicekey-ai
.\scripts\dev.ps1
```

脚本会在项目目录创建 `.venv`，安装本地识别依赖并启动程序。首次实际转写时需要下载 Whisper 模型；`small` 模型约数百 MB，耗时取决于网络。

启动后：

1. 保持识别方式为 `local`。
2. 点击“保存设置”。
3. 把光标放进任意文本框。
4. 按一次 `Alt + Q` 开始录音，再按一次完成。

同一进程内会缓存已加载模型，因此第一次转写通常比后续转写慢。

## 自定义快捷键

在主窗口的“全局快捷键”输入框中填写组合并保存。支持：

- 修饰键：`Ctrl`、`Alt`、`Shift`、`Win`
- 普通键：字母、数字、`F1–F12`、`Space`、`Enter`、`Tab`、`Esc`

示例：`Alt+Q`、`Ctrl+Shift+Space`、`Win+F8`。为避免拦截正常输入，不允许只设置单个字母。

## 可选的大模型校对

“大模型整理”默认关闭。开启后，模型只应执行轻量校对：修正标点、同音错字、重复语气词和专业术语，不回答口述中的问题。

### 手动配置兼容服务

1. 勾选“启用大模型整理”。
2. 配置来源选择 `manual`。
3. 填写 HTTPS API 地址、模型、协议和 Key。
4. 保存设置。

### 复用本机 Codex 配置（高级功能）

配置来源选择 `codex` 后，程序会读取：

```text
%USERPROFILE%\.codex\config.toml
%USERPROFILE%\.codex\auth.json
```

也支持用 `CODEX_HOME` 指向其他目录。程序不会修改这些文件，也不会把凭据复制进仓库；但启用润色后，转写文本、个人词库和凭据会用于访问配置中的 provider。

这不是所有使用者都应开启的默认功能。企业或共享账号应先确认组织安全政策和凭据授权范围。

## 模型与下载源

本地模型支持 `tiny`、`base`、`small`、`medium`、`large-v3`、`turbo`。CPU 用户建议先使用 `small`；模型越大通常越准确，也越慢、越占内存。

若无法直接访问 Hugging Face，可在“模型下载源”中填写镜像地址。镜像属于第三方供应链；对安全要求较高时，请自行下载并校验模型。

## 隐私与安全

默认设置：本地 ASR、关闭 LLM。此时正常转写不会上传录音或文字，但首次使用会连接模型下载源。

| 模式 | 会离开电脑的数据 |
| --- | --- |
| 本地 ASR，关闭 LLM | 无业务数据 |
| 云端 ASR | 录音、模型名和 API Key |
| 本地 ASR，开启 LLM | 转写文本、个人词库、模型名和 API Key |
| 云端 ASR，开启 LLM | 上述两类数据都会发送到各自服务 |

安全规则：

- 默认拒绝向远程 HTTP 地址发送 Key、录音或文本；请使用 HTTPS。
- “允许不安全 HTTP”只用于完全信任的隔离测试网络，可能泄露 Key 和内容。
- 配置保存在 `%APPDATA%\VoiceKeyAI\config.json`。
- 手动 Key 加密保存在 `%APPDATA%\VoiceKeyAI\secrets.json`。
- 临时 WAV 处理后删除；启动时清理超过 24 小时的 VoiceKey 临时文件。
- 当前 Release 若没有数字签名，Windows SmartScreen 可能提示未知发布者。

详情参见 [SECURITY.md](SECURITY.md)。

## 云端 ASR

如需使用兼容的 `/audio/transcriptions` 服务：

1. 将识别方式改为 `cloud`。
2. 填写 HTTPS API 地址、模型和 Key。
3. 保存后再录音。

启用后，录音会发送到你配置的服务。请自行确认服务方的数据保留、计费和隐私条款。

## 构建 EXE

```powershell
.\scripts\build.ps1
```

产物位于 `dist\VoiceKeyAI-v0.3.0.exe`。Whisper 模型不会打进 EXE，而是在首次使用时下载到用户缓存。

## 项目结构

```text
src/voicekey/
  app.py            GUI 与应用状态机
  audio.py          录音与临时文件清理
  hotkey.py         Windows 全局快捷键
  providers.py      本地/云端 ASR 与 LLM
  codex_config.py   可选的 Codex 配置读取
  secrets.py        Windows DPAPI 密钥存储
docs/
  architecture.md   架构与安全边界
  research.md       开源社区调研
```

## 开发与测试

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[local,dev]"
.\.venv\Scripts\python.exe -m pytest
```

CI 在 Windows 上运行测试。麦克风、快捷键、剪贴板和实际粘贴仍需真实桌面集成测试。

## 已知限制

- 当前是“按一次开始、再按一次结束”，不是按住说话。
- 云端 ASR 暂无流式中间字幕。
- 只能恢复纯文本剪贴板，不能完整恢复图片或复杂格式。
- 暂无托盘菜单、开机启动、签名安装器和自动更新。
- 普通权限程序无法向管理员权限窗口模拟粘贴。

## 参与贡献

请阅读 [CONTRIBUTING.md](CONTRIBUTING.md)。提交 Issue 时不要附带 API Key、私人录音或敏感转写。

## 许可证

[MIT License](LICENSE)
