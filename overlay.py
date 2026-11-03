"""Overlay opcional e leve em Tkinter. Não interage com o jogo."""

from __future__ import annotations

import ctypes
import queue
import sys
import threading
import tkinter as tk

BACKGROUND = "#15171e"
TIP_COLOR = "#f1f3f8"
STATUS_ONLINE = "#5ad08a"
STATUS_WAITING = "#f2b84b"
STATUS_OFFLINE = "#8a91a3"
WINDOW_ALPHA = 0.93
DWMWA_USE_IMMERSIVE_DARK_MODE = 20


def status_color(text: str) -> str:
    """Cor do status: verde em partida, âmbar esperando, cinza fora."""
    if text.startswith("○"):
        return STATUS_OFFLINE
    if "reconectando" in text or "aguardando" in text:
        return STATUS_WAITING
    return STATUS_ONLINE


def _use_dark_title_bar(root):
    """Barra de título escura no Windows 10 (20H1+) e 11; ignorada nos demais."""
    if sys.platform != "win32":
        return
    try:
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        enabled = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(enabled), ctypes.sizeof(enabled)
        )
    except (AttributeError, OSError):
        pass


class CoachOverlay:
    def __init__(self, enabled=True):
        self.enabled = enabled
        self.events = queue.Queue()
        self.root = None
        self.label = None
        self.status = None
        if enabled:
            self.thread = threading.Thread(target=self._run, daemon=True)
            self.thread.start()

    def _run(self):
        self.root = tk.Tk()
        self.root.title("LoL AI Coach")
        self.root.geometry("420x120+20+20")
        self.root.configure(bg=BACKGROUND)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", WINDOW_ALPHA)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._close)
        initial_status = "● Coach conectado"
        self.status = tk.Label(
            self.root, text=initial_status, font=("Segoe UI Semibold", 9), anchor="w",
            bg=BACKGROUND, fg=status_color(initial_status),
        )
        self.status.pack(fill="x", padx=12, pady=(10, 2))
        self.label = tk.Label(
            self.root, text="Esperando uma partida...", font=("Segoe UI", 11), wraplength=390,
            justify="left", anchor="nw", bg=BACKGROUND, fg=TIP_COLOR,
        )
        self.label.pack(fill="both", expand=True, padx=12, pady=(2, 10))
        # A janela precisa existir para receber o atributo; esconder e mostrar
        # de novo faz o Windows redesenhar a barra de título já escura.
        self.root.withdraw()
        self.root.update_idletasks()
        _use_dark_title_bar(self.root)
        self.root.deiconify()
        self.root.after(200, self._poll)
        self.root.mainloop()

    def _close(self):
        self.enabled = False
        while True:
            try:
                self.events.get_nowait()
            except queue.Empty:
                break
        if self.root is not None:
            self.root.destroy()
            self.root = None

    def _poll(self):
        if not self.root:
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status":
                    self.status.config(text=value, fg=status_color(value))
                elif kind == "tip":
                    self.label.config(text=value)
        except queue.Empty:
            pass
        self.root.after(200, self._poll)

    def set_status(self, text):
        if self.enabled:
            self.events.put(("status", text))

    def show_tip(self, text):
        if self.enabled:
            self.events.put(("tip", text))
