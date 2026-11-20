"""Windows desktop controls for the RoastSee NEXT bridge."""

from __future__ import annotations

import asyncio
from contextlib import suppress
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .artisan_next_poll import default_state_path
from .artisan_setup import artisan_configured, configure_artisan, restore_artisan
from .next_ble_bridge import NextBleBridge
from .state_store import StateStore

TITLE = "RoastSee NEXT for Artisan"
LANGUAGES = ("zh-CN", "en")
SYSTEM_LANGUAGE = "zh-CN" if ctypes.windll.kernel32.GetUserDefaultUILanguage() & 0x3FF == 4 else "en"
TEXT = {
    "subtitle": ("Artisan 蓝牙桥接", "Bluetooth bridge for Artisan"),
    "bluetooth": ("NEXT 蓝牙", "NEXT Bluetooth"),
    "connect": ("连接 NEXT", "Connect NEXT"),
    "disconnect": ("断开连接", "Disconnect"),
    "auto_start": ("连接后自动开始测量", "Start measurement on connection"),
    "idle": ("就绪，等待连接", "Ready to connect"),
    "scanning": ("正在搜索 RoastSee NEXT…", "Searching for RoastSee NEXT…"),
    "connecting": ("正在连接设备…", "Connecting…"),
    "waiting": ("已连接，请在 NEXT 上开始测量。", "Connected. Start measurement on NEXT."),
    "receiving": ("正在接收实时数据", "Receiving live readings"),
    "retrying": ("连接中断或设备未找到。请检查蓝牙及手机 App，正在重试。", "Connection unavailable. Check Bluetooth and the phone app. Retrying."),
    "storage_error": ("已连接，实时数据暂时无法写入。", "Connected. Unable to write live readings."),
    "stopping": ("正在断开蓝牙…", "Disconnecting…"),
    "error": ("桥接无法继续。", "The bridge session ended."),
    "agtron": ("色值 · Agtron", "Agtron"),
    "voice": ("声学活动", "Voice"),
    "rate": ("色值变化率", "Agtron rate"),
    "variation": ("色值波动量", "Agtron variation"),
    "artisan": ("Artisan 采样", "Artisan sampling"),
    "setup": ("配置并打开 Artisan", "Set up and open Artisan"),
    "open": ("打开 Artisan", "Open Artisan"),
    "restore": ("恢复原设置", "Restore settings"),
    "setup_help": ("自动添加色值、声学活动、变化率和波动量。", "Sets up Agtron, voice, rate and variation."),
    "ready_help": ("在 Artisan 点 ON 查看数据，点 START 开始记录。", "In Artisan, select ON to view readings and START to record."),
    "close_artisan": ("请先保存当前记录并退出 Artisan，再继续。", "Save your work and exit Artisan before continuing."),
    "choose_artisan": ("选择已安装的 artisan.exe", "Select the installed artisan.exe"),
    "invalid_artisan": ("请选择 Artisan 安装目录里的 artisan.exe。", "Choose artisan.exe in the Artisan installation folder."),
    "confirm_setup": (
        "将备份当前设置，把 Artisan 的 ET / BT 主采样源切换为 NEXT 桥接，并添加四路数据。使用原烘焙机采样时，可在这里恢复。",
        "This backs up your settings, switches Artisan's main ET/BT input to the NEXT bridge and adds four readings. Use Restore settings to switch back.",
    ),
    "confirm_restore": (
        "将恢复自动配置前的 Artisan 采样和通道设置。",
        "Restore the Artisan input and channel settings from before automatic setup?",
    ),
    "restored": ("已恢复 Artisan 原设置。", "Previous Artisan settings restored."),
    "already_open": ("Artisan 已打开。在 Artisan 点 ON 查看数据。", "Artisan is open. Select ON in Artisan to view readings."),
    "one_window": ("桥接窗口已经打开。", "The bridge is already open."),
    "save_language_error": ("语言已切换，无法保存本次选择。", "Language changed. The preference could not be saved."),
}


def load_language(path):
    try:
        preference = path.read_text(encoding="ascii").strip()
        if preference in LANGUAGES:
            return preference
    except (OSError, UnicodeError):
        pass
    return SYSTEM_LANGUAGE


def find_artisan():
    for location in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        if value := os.environ.get(location):
            folder = Path(value) / "Programs" if location == "LOCALAPPDATA" else Path(value)
            executable = folder / "Artisan" / "artisan.exe"
            if executable.is_file():
                return executable
    return None


def artisan_running():
    tasklist = Path(os.environ["SystemRoot"]) / "System32" / "tasklist.exe"
    result = subprocess.run(
        [str(tasklist), "/FI", "IMAGENAME eq artisan.exe", "/FO", "CSV", "/NH"],
        capture_output=True, check=True, timeout=5, creationflags=subprocess.CREATE_NO_WINDOW,
    )
    return any(line.lower().startswith(b'"artisan.exe",') for line in result.stdout.splitlines())


def launch_artisan(executable):
    frozen_libs = getattr(sys, "_MEIPASS", None)
    if frozen_libs:
        ctypes.windll.kernel32.SetDllDirectoryW(None)
    try:
        subprocess.Popen(
            [str(executable)], cwd=executable.parent,
            env={**os.environ, "PYINSTALLER_RESET_ENVIRONMENT": "1"},
        )
    finally:
        if frozen_libs:
            ctypes.windll.kernel32.SetDllDirectoryW(ctypes.c_wchar_p(frozen_libs))


class BleSession:
    def __init__(self, state, auto_start):
        self.state = state
        self.stop = threading.Event()
        self.snapshot = ("scanning", "", None)
        self.bridge = NextBleBridge(
            StateStore(state), auto_start_live=auto_start,
            on_status=self.set_status, on_sample=self.set_sample,
        )
        self.thread = threading.Thread(target=self.run, daemon=True)

    def set_status(self, status, detail):
        if status in ("scanning", "retrying"):
            self.state.unlink(missing_ok=True)
        self.snapshot = (status, detail, None)

    def set_sample(self, reading):
        self.snapshot = ("receiving", "", reading)

    def run(self):
        try:
            try:
                asyncio.run(self.receive())
            finally:
                self.state.unlink(missing_ok=True)
        except Exception as exc:
            self.snapshot = ("error", str(exc), None)

    async def receive(self):
        task = asyncio.create_task(self.bridge.run_forever())
        try:
            while not self.stop.is_set() and not task.done():
                await asyncio.sleep(0.1)
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


class BridgeWindow:
    def __init__(self, root, poller):
        self.root = root
        self.poller = poller
        self.state = default_state_path().with_name("desktop-latest.json")
        self.backup = self.state.with_name("artisan-settings-backup.json")
        self.language_path = self.state.with_name("desktop-language.txt")
        self.language = load_language(self.language_path)
        self.labels = {}
        self.artisan = find_artisan()
        self.session = None
        self.closing = False
        self.auto_start = tk.BooleanVar(root)
        self.link_status = tk.StringVar(root, self.t("idle"))
        self.setup_status = tk.StringVar(root)
        self.readings = [tk.StringVar(root, "—") for _ in range(4)]

        root.title(TITLE)
        root.configure(bg="#EFF3F6")
        root.minsize(600, 1)
        font = "Microsoft YaHei UI" if SYSTEM_LANGUAGE == "zh-CN" else "Segoe UI"
        root.option_add("*Font", (font, 10))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<FocusIn>", self.check_setup)
        icon = poller.parent / "assets" / "brand" / "lebrew.ico"
        if icon.is_file():
            root.iconbitmap(default=str(icon))

        style = ttk.Style(root)
        style.theme_use("clam")
        style.configure("TButton", padding=(13, 8))
        style.configure("Primary.TButton", background="#155E75", foreground="#FFFFFF")
        style.map("Primary.TButton", background=[("disabled", "#E5E9ED"), ("active", "#104D61")],
                  foreground=[("disabled", "#657384")])
        style.configure("TCheckbutton", background="#FFFFFF", foreground="#253A4C")
        style.map("TCheckbutton", background=[("active", "#FFFFFF")])
        style.configure("TLabel", background="#FFFFFF", foreground="#172C3D")
        style.configure("Section.TLabel", font=(font, 12, "bold"))
        style.configure("Status.TLabel", foreground="#496276")
        style.configure("Metric.TLabel", font=("Segoe UI", 23, "bold"))

        header = tk.Frame(root, bg="#162B3B", padx=24, pady=18)
        header.pack(fill="x")
        header.columnconfigure(0, weight=1)
        tk.Label(header, text="RoastSee NEXT", font=("Segoe UI", 22, "bold"),
                 fg="#FFFFFF", bg="#162B3B").grid(row=0, column=0, sticky="w")
        tk.Label(header, textvariable=self.label("subtitle"), fg="#BED0DB", bg="#162B3B").grid(row=1, column=0, sticky="w")
        self.language_picker = ttk.Combobox(
            header, state="readonly", values=("简体中文", "English"), width=10,
        )
        self.language_picker.current(LANGUAGES.index(self.language))
        self.language_picker.grid(row=0, column=1, sticky="e", padx=(10, 0))
        self.language_picker.bind("<<ComboboxSelected>>", self.change_language)

        link = self.section("bluetooth")
        self.connect_button = ttk.Button(link, text=self.t("connect"), style="Primary.TButton", command=self.toggle)
        self.connect_button.grid(row=0, column=1, sticky="e")
        ttk.Label(link, textvariable=self.link_status, style="Status.TLabel", wraplength=520).grid(
            row=1, columnspan=2, sticky="w", pady=(9, 7)
        )
        self.checkbox = ttk.Checkbutton(link, textvariable=self.label("auto_start"), variable=self.auto_start)
        self.checkbox.grid(row=2, columnspan=2, sticky="w")
        ttk.Separator(link).grid(row=3, columnspan=2, sticky="ew", pady=(15, 12))
        metrics = tk.Frame(link, bg="#FFFFFF")
        metrics.grid(row=4, columnspan=2, sticky="ew")
        for column, (label, value) in enumerate(zip(("agtron", "voice", "rate", "variation"), self.readings)):
            metrics.columnconfigure(column, weight=1, uniform="reading")
            ttk.Label(metrics, textvariable=self.label(label), style="Status.TLabel").grid(row=0, column=column, sticky="w")
            ttk.Label(metrics, textvariable=value, style="Metric.TLabel").grid(row=1, column=column, sticky="w")

        setup = self.section("artisan")
        ttk.Label(setup, textvariable=self.setup_status, style="Status.TLabel", wraplength=520).grid(
            row=1, columnspan=2, sticky="w", pady=(8, 13)
        )
        actions = tk.Frame(setup, bg="#FFFFFF")
        actions.grid(row=2, columnspan=2, sticky="w")
        self.setup_button = ttk.Button(actions, style="Primary.TButton", command=self.setup_artisan)
        self.setup_button.pack(side="left")
        self.restore_button = ttk.Button(actions, textvariable=self.label("restore"), command=self.restore)
        self.restore_button.pack(side="left", padx=(9, 0))
        self.connect_button.focus_set()
        self.check_setup()
        self.refresh_link()

    def t(self, key):
        return TEXT[key][LANGUAGES.index(self.language)]

    def label(self, key):
        self.labels[key] = tk.StringVar(self.root, self.t(key))
        return self.labels[key]

    def change_language(self, _event=None):
        self.language = LANGUAGES[self.language_picker.current()]
        for key, label in self.labels.items():
            label.set(self.t(key))
        self.check_setup()
        self.render_link()
        try:
            self.language_path.parent.mkdir(parents=True, exist_ok=True)
            self.language_path.write_text(self.language, encoding="ascii")
        except OSError as exc:
            messagebox.showwarning(TITLE, f"{self.t('save_language_error')}\n{exc}", parent=self.root)

    def section(self, name):
        frame = tk.Frame(self.root, bg="#FFFFFF", padx=18, pady=15,
                         highlightbackground="#DAE4EB", highlightthickness=1)
        frame.pack(fill="x", padx=20, pady=(15, 0 if name == "bluetooth" else 20))
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, textvariable=self.label(name), style="Section.TLabel").grid(row=0, column=0, sticky="w")
        return frame

    def check_setup(self, event=None):
        try:
            configured = artisan_configured(self.poller, self.state)
        except (OSError, ValueError) as exc:
            configured = False
            self.setup_status.set(str(exc))
        else:
            self.setup_status.set(self.t("ready_help" if configured else "setup_help"))
        self.setup_button.configure(text=self.t("open" if configured else "setup"))
        self.restore_button.state(["!disabled"] if self.backup.is_file() else ["disabled"])

    def setup_artisan(self):
        try:
            configured = artisan_configured(self.poller, self.state)
            if artisan_running():
                self.setup_status.set(self.t("already_open" if configured else "close_artisan"))
                return
            if self.artisan is None or not self.artisan.is_file():
                filename = filedialog.askopenfilename(
                    parent=self.root, title=self.t("choose_artisan"), filetypes=[("Artisan", "artisan.exe")],
                )
                if not filename:
                    return
                if Path(filename).name.lower() != "artisan.exe":
                    raise ValueError(self.t("invalid_artisan"))
                self.artisan = Path(filename)
            if not configured:
                if not messagebox.askokcancel(
                    self.t("setup"), self.t("confirm_setup"), parent=self.root, default=messagebox.CANCEL,
                ):
                    return
                if artisan_running():
                    messagebox.showinfo(TITLE, self.t("close_artisan"), parent=self.root)
                    return
                configure_artisan(self.poller, self.state, self.backup)
            launch_artisan(self.artisan)
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.root)
        self.check_setup()

    def restore(self):
        try:
            if not messagebox.askokcancel(self.t("restore"), self.t("confirm_restore"), parent=self.root):
                return
            if artisan_running():
                messagebox.showinfo(TITLE, self.t("close_artisan"), parent=self.root)
                return
            restore_artisan(self.backup)
            self.check_setup()
            self.setup_status.set(self.t("restored"))
        except (OSError, ValueError, subprocess.SubprocessError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.root)

    def toggle(self):
        if self.session is None:
            self.session = BleSession(self.state, self.auto_start.get())
            self.session.thread.start()
        else:
            self.session.stop.set()
        self.render_link()

    def render_link(self):
        session = self.session
        if session is None:
            status, detail, reading = "idle", "", None
        else:
            status, detail, reading = session.snapshot
            if not session.thread.is_alive():
                self.session = None
                if status != "error":
                    status, detail, reading = "idle", "", None
            elif session.stop.is_set():
                status, detail, reading = "stopping", "", None
        self.link_status.set(self.t(status) + ("\n" + detail if detail else ""))
        self.connect_button.configure(text=self.t("connect" if self.session is None else "disconnect"))
        self.connect_button.state(["disabled"] if status == "stopping" else ["!disabled"])
        self.checkbox.state(["!disabled"] if self.session is None else ["disabled"])
        for key, label in zip(("curve_agtron", "voice", "agtron_rate", "weighted_median_mean_agtron"), self.readings):
            label.set(f"{reading[key]:.3g}" if reading is not None else "—")

    def refresh_link(self):
        if self.session is not None:
            self.render_link()
        if self.closing and self.session is None:
            self.root.destroy()
        else:
            self.root.after(150, self.refresh_link)

    def close(self):
        self.closing = True
        if self.session is not None:
            self.session.stop.set()


def main():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    create_mutex = kernel.CreateMutexW
    create_mutex.argtypes = (ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR)
    create_mutex.restype = wintypes.HANDLE
    handle = create_mutex(None, False, r"Local\LeBrew-RoastSeeNEXT-Artisan")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    already_open = ctypes.get_last_error() == 183
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    try:
        if already_open:
            language = load_language(default_state_path().with_name("desktop-language.txt"))
            ctypes.windll.user32.MessageBoxW(None, TEXT["one_window"][LANGUAGES.index(language)], TITLE, 0x40)
            return
        if getattr(sys, "frozen", False):
            bundle = Path(sys.executable).parent
        else:
            bundle = Path(__file__).resolve().parents[1] / "dist/windows/RoastSeeNEXT-Artisan-Windows-x64"
        root = tk.Tk()
        BridgeWindow(root, bundle / "artisan_next_poll.exe")
        root.mainloop()
    finally:
        kernel.CloseHandle(handle)


if __name__ == "__main__":
    main()
