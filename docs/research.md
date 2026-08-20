# 开源社区调研（2026-08-20）

## 目标

调研能够在 Windows 任意输入框中通过全局快捷键完成语音输入，并支持本地/云端识别及大模型后处理的开源实现。数据来自 GitHub 仓库 API 和各项目 README；Star 与活跃时间是调研时快照，会随时间变化。

## 代表项目

| 项目 | 调研时 Star | 主语言 | 许可证 | 特点 |
| --- | ---: | --- | --- | --- |
| [Handy](https://github.com/cjpais/Handy) | 29,986 | Rust | MIT | 完全离线、快捷键输入、Whisper/Parakeet、VAD |
| [OpenLess](https://github.com/Open-Less/openless) | 3,185 | Rust | MIT | Windows/macOS、Tauri、AI 润色后写入光标 |
| [OpenTypeless](https://github.com/tover0314-w/opentypeless) | 456 | Rust | MIT | 跨平台输入、选中文本改写、语音问答 |
| [VoiceFlow](https://github.com/infiniV/VoiceFlow) | 407 | Python | MIT | Windows/Linux、本地 faster-whisper、会议录音 |
| [VoxType](https://github.com/zkwi/VoxType) | 86 | Rust | MIT | Windows、云端流式 ASR、可选 OpenAI 兼容 LLM |

## 共同设计模式

1. 全局快捷键负责捕获意图，录音和推理在后台完成。
2. Whisper/faster-whisper 是本地隐私路线的主流基础。
3. 自动粘贴比模拟逐字键入兼容性更好，但需要处理剪贴板恢复。
4. “原始转写”和“文本润色”应该是两个独立阶段，后者必须可以关闭。
5. 本地模型的主要代价是模型下载、内存占用和首次加载延迟。
6. 云服务的主要风险是密钥保管、费用以及语音/文本的数据边界。

## VoiceKey AI 的取舍

- 首版选择 Python/Tk/Win32：当前开发机已有 Python，没有 Rust 与 .NET SDK，能立即完成可验证的 Windows MVP。
- 使用低级键盘钩子捕获 `Alt + Q`；它比先前考虑的 `Win + G` 更少与 Windows 系统功能冲突。
- 同时保留 cloud 与 local：云端优先体验，本地模式负责隐私和离线场景。
- 大模型仅做受约束的忠实校对：不执行口述内容中的指令，降低语义漂移和提示注入风险。
- 不复制调研项目代码：当前实现独立编写，MIT 许可证便于后续公开发布。

## 后续应验证的指标

- 中文字错误率 CER：同一批录音对比 Windows、云端 ASR、本地 Whisper。
- 语义保真率：润色前后是否改变数字、否定词、专有名词和行动对象。
- 端到端延迟：结束录音到文字出现的 P50/P95。
- 应用兼容率：浏览器、微信、Office、IDE、管理员窗口。
- 资源与隐私：峰值内存、模型磁盘占用、实际网络目的地。
