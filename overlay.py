"""Overlay opcional e leve em Tkinter. Não interage com o jogo."""

from __future__ import annotations

import queue
import threading
import tkinter as tk


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
        self.root.attributes("-topmost", True)
        self.root.resizable(False, False)
        self.status = tk.Label(self.root, text="● Coach conectado", font=("Segoe UI", 9), anchor="w")
        self.status.pack(fill="x", padx=12, pady=(10, 2))
        self.label = tk.Label(self.root, text="Esperando uma partida...", font=("Segoe UI", 11), wraplength=390, justify="left", anchor="w")
        self.label.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        self.root.after(200, self._poll)
        self.root.mainloop()

    def _poll(self):
        if not self.root:
            return
        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "status": self.status.config(text=value)
                elif kind == "tip": self.label.config(text=value)
        except queue.Empty:
            pass
        self.root.after(200, self._poll)

    def set_status(self, text):
        if self.enabled: self.events.put(("status", text))

    def show_tip(self, text):
        if self.enabled: self.events.put(("tip", text))
