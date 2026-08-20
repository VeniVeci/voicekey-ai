from __future__ import annotations

import os
import queue
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

from .audio import AudioRecorder, cleanup_stale_recordings
from .codex_config import load_codex_connection
from .config import AppSettings, load_settings, save_settings
from .hotkey import GlobalHotkey, HotkeyError, normalize_hotkey
from .injector import paste_shortcut
from .providers import ProviderError, polish_text, transcribe_cloud, transcribe_local
from .secrets import SecretStore


COLORS = {
    "background": "#10141f",
    "panel": "#171d2b",
    "text": "#eef3ff",
    "muted": "#9aa7bd",
    "accent": "#65d6ad",
    "recording": "#ff667d",
    "working": "#f8c15c",
}


class CheckToggle(tk.Frame):
    """Theme-independent checkbox that always renders a real check mark."""

    def __init__(self, parent, text: str, variable: tk.BooleanVar):
        super().__init__(parent, bg=COLORS["background"], cursor="hand2", takefocus=True)
        self.variable = variable
        self.canvas = tk.Canvas(self, width=22, height=22, bg=COLORS["background"], highlightthickness=0)
        self.canvas.pack(side="left")
        self.label = tk.Label(
            self, text=text, bg=COLORS["background"], fg=COLORS["text"],
            font=("Microsoft YaHei UI", 10), cursor="hand2",
        )
        self.label.pack(side="left", padx=(7, 0))
        for widget in (self, self.canvas, self.label):
            widget.bind("<Button-1>", self._toggle)
        self.bind("<space>", self._toggle)
        self.variable.trace_add("write", lambda *_: self._draw())
        self._draw()

    def _toggle(self, _event=None):
        self.variable.set(not self.variable.get())
        return "break"

    def _draw(self) -> None:
        self.canvas.delete("all")
        selected = self.variable.get()
        fill = COLORS["accent"] if selected else COLORS["panel"]
        outline = COLORS["accent"] if selected else COLORS["muted"]
        self.canvas.create_rectangle(2, 2, 20, 20, fill=fill, outline=outline, width=2)
        if selected:
            self.canvas.create_line(6, 11, 10, 15, 17, 7, fill="#0a2119", width=3, capstyle="round", joinstyle="round")


class VoiceKeyApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        cleanup_stale_recordings()
        self.settings = load_settings()
        self.secret_store = SecretStore()
        self.secrets = self.secret_store.load()
        self.recorder = AudioRecorder(self.settings.sample_rate)
        self.busy = False
        self.hotkey_events: queue.SimpleQueue[bool] = queue.SimpleQueue()
        self.hotkey_var = tk.StringVar(value=self.settings.hotkey)
        self.shortcut_hint = tk.StringVar(value=self._shortcut_instruction())
        self.shortcut_footer = tk.StringVar(value=f"全局快捷键：{self.settings.hotkey}")
        self.hotkey = GlobalHotkey(self.settings.hotkey, lambda: self.hotkey_events.put(True))
        self._build_window()
        self._build_overlay()
        self._load_form()
        self.hotkey.start()
        self.root.after(50, self._poll_hotkey)
        self.root.after(250, self._check_hotkey)
        self.root.protocol("WM_DELETE_WINDOW", self.shutdown)

    def _poll_hotkey(self) -> None:
        try:
            self.hotkey_events.get_nowait()
        except queue.Empty:
            pass
        else:
            self.toggle_recording()
        self.root.after(50, self._poll_hotkey)

    def _check_hotkey(self) -> None:
        if self.hotkey.ready.is_set() and self.hotkey.error:
            self._fail(f"{self.settings.hotkey} 快捷键安装失败：{self.hotkey.error}")

    def _shortcut_instruction(self) -> str:
        return f"按 {self.settings.hotkey.replace('+', ' + ')} 开始说话，再按一次完成；结果会写入当前光标位置。"

    def _build_window(self) -> None:
        self.root.title("VoiceKey AI")
        self.root.geometry("700x680")
        self.root.minsize(640, 600)
        self.root.configure(bg=COLORS["background"])
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TFrame", background=COLORS["background"])
        style.configure("Card.TFrame", background=COLORS["panel"])
        style.configure("TLabel", background=COLORS["background"], foreground=COLORS["text"])
        style.configure("Card.TLabel", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Hint.Card.TLabel", background=COLORS["panel"], foreground=COLORS["muted"])
        style.configure("TCheckbutton", background=COLORS["panel"], foreground=COLORS["text"])
        style.configure("Accent.TButton", font=("Microsoft YaHei UI", 11, "bold"))

        outer = ttk.Frame(self.root, padding=24)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="VoiceKey AI", font=("Segoe UI", 24, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            textvariable=self.shortcut_hint,
            foreground=COLORS["muted"],
        ).pack(anchor="w", pady=(4, 18))

        self.status_var = tk.StringVar(value="就绪")
        status_card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        status_card.pack(fill="x", pady=(0, 14))
        ttk.Label(status_card, text="当前状态", style="Hint.Card.TLabel").pack(anchor="w")
        ttk.Label(status_card, textvariable=self.status_var, style="Card.TLabel", font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w", pady=(5, 0))
        shortcut_row = ttk.Frame(status_card, style="Card.TFrame")
        shortcut_row.pack(fill="x", pady=(12, 0))
        ttk.Label(shortcut_row, text="全局快捷键", style="Hint.Card.TLabel").pack(side="left")
        ttk.Entry(shortcut_row, textvariable=self.hotkey_var, width=22).pack(side="left", padx=(12, 8))
        ttk.Label(shortcut_row, text="例如 Alt+Q、Ctrl+Shift+Space、Win+F8", style="Hint.Card.TLabel").pack(side="left")

        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)
        asr_tab = ttk.Frame(notebook, padding=16)
        polish_tab = ttk.Frame(notebook, padding=16)
        notebook.add(asr_tab, text="语音识别")
        notebook.add(polish_tab, text="大模型整理")

        self.asr_backend = tk.StringVar()
        self.asr_base = tk.StringVar()
        self.asr_model = tk.StringVar()
        self.asr_language = tk.StringVar()
        self.asr_key = tk.StringVar()
        self.local_model = tk.StringVar()
        self.hf_endpoint = tk.StringVar()
        self.polish_enabled = tk.BooleanVar()
        self.polish_source = tk.StringVar()
        self.polish_base = tk.StringVar()
        self.polish_model = tk.StringVar()
        self.polish_protocol = tk.StringVar()
        self.polish_key = tk.StringVar()
        self.glossary = tk.StringVar()
        self.allow_insecure_http = tk.BooleanVar()

        self._row(asr_tab, 0, "识别方式", ttk.Combobox(asr_tab, textvariable=self.asr_backend, values=("cloud", "local"), state="readonly"), "cloud 使用兼容接口；local 使用 faster-whisper")
        self._row(asr_tab, 1, "API 地址", ttk.Entry(asr_tab, textvariable=self.asr_base), "例如 https://api.openai.com/v1")
        self._row(asr_tab, 2, "ASR 模型", ttk.Entry(asr_tab, textvariable=self.asr_model), "例如 gpt-4o-mini-transcribe")
        self._row(asr_tab, 3, "语言", ttk.Entry(asr_tab, textvariable=self.asr_language), "中文填 zh；自动检测可留空")
        self._row(asr_tab, 4, "ASR 密钥", ttk.Entry(asr_tab, textvariable=self.asr_key, show="•"), "使用 Windows DPAPI 加密，仅当前 Windows 用户可解密")
        self._row(asr_tab, 5, "本地模型", ttk.Entry(asr_tab, textvariable=self.local_model), "tiny / base / small / medium / large-v3 / turbo")
        self._row(asr_tab, 6, "模型下载源", ttk.Entry(asr_tab, textvariable=self.hf_endpoint), "可选；中国大陆可填写 https://hf-mirror.com")

        CheckToggle(polish_tab, text="启用大模型整理", variable=self.polish_enabled).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        self._row(polish_tab, 1, "配置来源", ttk.Combobox(polish_tab, textvariable=self.polish_source, values=("codex", "manual"), state="readonly"), "codex 自动读取 ~/.codex/config.toml 与 auth.json")
        self._row(polish_tab, 2, "API 地址", ttk.Entry(polish_tab, textvariable=self.polish_base), "manual 模式使用；Codex 模式会动态读取")
        self._row(polish_tab, 3, "模型", ttk.Entry(polish_tab, textvariable=self.polish_model), "当前指定为 gpt-5.6-luna")
        self._row(polish_tab, 4, "API 协议", ttk.Combobox(polish_tab, textvariable=self.polish_protocol, values=("responses", "chat_completions"), state="readonly"), "Codex 模式会采用 provider 的 wire_api")
        self._row(polish_tab, 5, "模型密钥", ttk.Entry(polish_tab, textvariable=self.polish_key, show="•"), "仅 manual 模式使用；DPAPI 加密保存")
        self._row(polish_tab, 6, "个人词库", ttk.Entry(polish_tab, textvariable=self.glossary), "逗号分隔项目名、人名和技术词")
        CheckToggle(polish_tab, text="允许远程服务使用不安全的 HTTP（可能泄露 Key 和文本）", variable=self.allow_insecure_http).grid(row=14, column=0, columnspan=2, sticky="w", pady=(10, 0))

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(16, 0))
        ttk.Button(actions, text="保存设置", style="Accent.TButton", command=self.save_form).pack(side="left")
        ttk.Button(actions, text="隐藏窗口", command=self.root.iconify).pack(side="left", padx=10)
        ttk.Label(actions, textvariable=self.shortcut_footer, foreground=COLORS["muted"]).pack(side="right")

    @staticmethod
    def _row(parent, row: int, label: str, widget, hint: str) -> None:
        parent.columnconfigure(1, weight=1)
        ttk.Label(parent, text=label).grid(row=row * 2, column=0, sticky="w", padx=(0, 12), pady=(7, 2))
        widget.grid(row=row * 2, column=1, sticky="ew", pady=(7, 2))
        ttk.Label(parent, text=hint, foreground=COLORS["muted"]).grid(row=row * 2 + 1, column=1, sticky="w", pady=(0, 5))

    def _build_overlay(self) -> None:
        self.overlay = tk.Toplevel(self.root)
        self.overlay.withdraw()
        self.overlay.overrideredirect(True)
        self.overlay.attributes("-topmost", True)
        self.overlay.configure(bg=COLORS["panel"])
        self.overlay_label = tk.Label(
            self.overlay,
            text="",
            bg=COLORS["panel"],
            fg=COLORS["text"],
            font=("Microsoft YaHei UI", 12, "bold"),
            padx=24,
            pady=13,
        )
        self.overlay_label.pack()

    def _show_overlay(self, text: str, color: str, auto_hide_ms: int | None = None) -> None:
        self.overlay_label.configure(text=text, fg=color)
        self.overlay.update_idletasks()
        width = self.overlay.winfo_reqwidth()
        height = self.overlay.winfo_reqheight()
        x = (self.overlay.winfo_screenwidth() - width) // 2
        y = self.overlay.winfo_screenheight() - height - 90
        self.overlay.geometry(f"+{x}+{y}")
        self.overlay.deiconify()
        if auto_hide_ms:
            self.root.after(auto_hide_ms, self.overlay.withdraw)

    def _load_form(self) -> None:
        self.asr_backend.set(self.settings.asr.backend)
        self.asr_base.set(self.settings.asr.base_url)
        self.asr_model.set(self.settings.asr.model)
        self.asr_language.set(self.settings.asr.language)
        self.asr_key.set(self.secrets.get("asr_api_key", ""))
        self.local_model.set(self.settings.asr.local_model)
        self.hf_endpoint.set(self.settings.asr.hf_endpoint)
        self.polish_enabled.set(self.settings.polish.enabled)
        self.polish_source.set(self.settings.polish.credential_source)
        self.polish_base.set(self.settings.polish.base_url)
        self.polish_model.set(self.settings.polish.model)
        self.polish_protocol.set(self.settings.polish.api_protocol)
        self.polish_key.set(self.secrets.get("polish_api_key", ""))
        self.glossary.set(self.settings.glossary)
        self.allow_insecure_http.set(self.settings.allow_insecure_http)
        if self.settings.polish.credential_source == "codex":
            try:
                connection = load_codex_connection()
                self.polish_base.set(connection.base_url)
                self.polish_protocol.set(connection.wire_api)
                self.status_var.set(f"已读取 Codex 配置：{connection.provider_name} / {self.settings.polish.model}")
            except Exception as error:
                self.status_var.set(f"Codex 配置暂不可用：{error}")

    def _apply_hotkey(self) -> bool:
        try:
            shortcut = normalize_hotkey(self.hotkey_var.get())
        except HotkeyError as error:
            messagebox.showerror("快捷键无效", str(error))
            return False
        self.hotkey_var.set(shortcut)
        if shortcut == self.settings.hotkey:
            return True
        old_shortcut = self.settings.hotkey
        self.hotkey.stop()
        replacement = GlobalHotkey(shortcut, lambda: self.hotkey_events.put(True))
        replacement.start()
        replacement.ready.wait(timeout=1)
        if replacement.error or not replacement._hook:
            replacement.stop()
            self.hotkey = GlobalHotkey(old_shortcut, lambda: self.hotkey_events.put(True))
            self.hotkey.start()
            messagebox.showerror("快捷键设置失败", str(replacement.error or "无法安装全局快捷键"))
            self.hotkey_var.set(old_shortcut)
            return False
        self.hotkey = replacement
        self.settings.hotkey = shortcut
        self.shortcut_hint.set(self._shortcut_instruction())
        self.shortcut_footer.set(f"全局快捷键：{shortcut}")
        return True

    def save_form(self, notify: bool = True) -> bool:
        if not self._apply_hotkey():
            return False
        self.settings.asr.backend = self.asr_backend.get().strip() or "cloud"
        self.settings.asr.base_url = self.asr_base.get().strip()
        self.settings.asr.model = self.asr_model.get().strip()
        self.settings.asr.language = self.asr_language.get().strip()
        self.settings.asr.local_model = self.local_model.get().strip() or "small"
        self.settings.asr.hf_endpoint = self.hf_endpoint.get().strip()
        self.settings.polish.enabled = self.polish_enabled.get()
        self.settings.polish.credential_source = self.polish_source.get().strip() or "codex"
        self.settings.polish.base_url = self.polish_base.get().strip()
        self.settings.polish.model = self.polish_model.get().strip()
        self.settings.polish.api_protocol = self.polish_protocol.get().strip() or "responses"
        self.settings.glossary = self.glossary.get().strip()
        self.settings.allow_insecure_http = self.allow_insecure_http.get()
        save_settings(self.settings)
        self.secret_store.save({
            "asr_api_key": self.asr_key.get().strip(),
            "polish_api_key": self.polish_key.get().strip(),
        })
        self.secrets = self.secret_store.load()
        if notify:
            self.status_var.set(f"设置已保存；按 {self.settings.hotkey} 开始")
        return True

    def toggle_recording(self) -> None:
        if self.busy:
            self._show_overlay("正在处理，请稍候…", COLORS["working"], 1200)
            return
        if self.recorder.is_recording:
            self._finish_recording()
        else:
            self._start_recording()

    def _start_recording(self) -> None:
        try:
            if not self.save_form(notify=False):
                return
            self.recorder = AudioRecorder(self.settings.sample_rate)
            self.recorder.start()
            self.status_var.set(f"正在录音；再按 {self.settings.hotkey} 完成")
            self._show_overlay(f"● 正在聆听，再按 {self.settings.hotkey} 完成", COLORS["recording"])
        except Exception as error:
            self._fail(f"无法开始录音：{error}")

    def _finish_recording(self) -> None:
        try:
            audio_path, duration = self.recorder.stop()
        except Exception as error:
            self._fail(f"无法停止录音：{error}")
            return
        if duration < self.settings.min_recording_seconds:
            audio_path.unlink(missing_ok=True)
            self.status_var.set("录音太短，已忽略")
            self._show_overlay("录音太短", COLORS["muted"], 1200)
            return
        self.busy = True
        self.status_var.set("正在识别并整理…")
        self._show_overlay("正在识别并整理…", COLORS["working"])
        threading.Thread(target=self._process_audio, args=(audio_path,), daemon=True).start()

    def _process_audio(self, audio_path: Path) -> None:
        try:
            started = time.perf_counter()
            if self.settings.asr.backend == "local":
                raw_text = transcribe_local(audio_path, self.settings)
            else:
                asr_key = self.secrets.get("asr_api_key") or os.getenv(self.settings.asr.api_key_env, "")
                raw_text = transcribe_cloud(audio_path, self.settings, asr_key)
            asr_seconds = time.perf_counter() - started
            polish_started = time.perf_counter()
            if self.settings.polish.credential_source == "codex":
                if self.settings.polish.enabled:
                    connection = load_codex_connection()
                    final_text = polish_text(
                        raw_text,
                        self.settings,
                        connection.api_key,
                        base_url=connection.base_url,
                        api_protocol=connection.wire_api,
                    )
                else:
                    final_text = raw_text
            else:
                polish_key = self.secrets.get("polish_api_key") or os.getenv(self.settings.polish.api_key_env, "")
                final_text = polish_text(raw_text, self.settings, polish_key)
            polish_seconds = time.perf_counter() - polish_started if self.settings.polish.enabled else 0.0
            self.root.after(0, lambda: self._deliver(final_text, asr_seconds, polish_seconds))
        except Exception as error:
            self.root.after(0, lambda err=error: self._fail(str(err)))
        finally:
            audio_path.unlink(missing_ok=True)

    def _deliver(self, text: str, asr_seconds: float, polish_seconds: float) -> None:
        previous = None
        try:
            previous = self.root.clipboard_get()
        except tk.TclError:
            pass
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.root.update()
        paste_shortcut()
        if self.settings.restore_clipboard and previous is not None:
            self.root.after(1200, lambda value=previous, inserted=text: self._restore_clipboard(value, inserted))
        self.busy = False
        timing = f"识别 {asr_seconds:.1f}s"
        if self.settings.polish.enabled:
            timing += f"，润色 {polish_seconds:.1f}s"
        self.status_var.set(f"完成（{timing}）：{text[:80]}")
        self._show_overlay("✓ 已输入", COLORS["accent"], 1200)

    def _restore_clipboard(self, value: str, inserted: str) -> None:
        try:
            if self.root.clipboard_get() != inserted:
                return
            self.root.clipboard_clear()
            self.root.clipboard_append(value)
            self.root.update()
        except tk.TclError:
            pass

    def _fail(self, message: str) -> None:
        self.busy = False
        self.status_var.set(message)
        self._show_overlay("处理失败，请查看主窗口", COLORS["recording"], 2200)
        self.root.deiconify()
        self.root.lift()

    def shutdown(self) -> None:
        try:
            self.recorder.cancel()
            self.hotkey.stop()
        finally:
            self.root.destroy()


def main() -> None:
    if os.name != "nt":
        raise SystemExit("VoiceKey AI currently supports Windows only.")
    root = tk.Tk()
    try:
        app = VoiceKeyApp(root)
        if os.getenv("VOICEKEY_SMOKE_TEST") == "1":
            root.after(700, app.shutdown)
        root.mainloop()
    except ProviderError as error:
        messagebox.showerror("VoiceKey AI", str(error))
