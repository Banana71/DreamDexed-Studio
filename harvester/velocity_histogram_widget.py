"""
velocity_histogram_widget.py – Lebendes Velocity‑Balken‑Widget
für DreamDexed Studio.
Empfängt Velocity‑Werte über eine queue.Queue und stellt sie
als verblassende Balken dar.
"""

import tkinter as tk
import queue
import time
from harvester.constants import COLOR_VELOCITY_BAR

# --- Konstanten ---
DEFAULT_WIDTH = 200
DEFAULT_HEIGHT = 32
DECAY_TIME = 1.6          # Sekunden
WHITE_DURATION = 0.15      # 200 ms weiß


def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


class VelocityHistogramWidget(tk.Frame):
    def __init__(self, parent, velocity_queue=None, bg="#1a1a1a",
                 width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT,
                 borderwidth=0, highlightthickness=1,
                 highlightbackground="white", relief="flat", **kwargs):
        super().__init__(parent, bg=bg, width=width, height=height,
                         borderwidth=borderwidth,
                         highlightthickness=highlightthickness,
                         highlightbackground=highlightbackground,
                         relief=relief, **kwargs)
        self.pack_propagate(False)

        self.velocity_queue = velocity_queue
        self.canvas = tk.Canvas(self, width=width, height=height,
                                bg=bg, highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.bg_color = bg
        self.bg_r, self.bg_g, self.bg_b = hex_to_rgb(self.bg_color)

        # Farbe für das Aufleuchten der Balken (aus constants.py)
        self.fg_r, self.fg_g, self.fg_b = hex_to_rgb(COLOR_VELOCITY_BAR)

        self.rects = []
        self.start_times = []
        self.active = set()

        self._num_velocities = 128
        self._build_bars(128, width, height)

        self._after_id = None
        self._start_update_loop()

    def set_dimensions(self, width, height):
        self.config(width=width, height=height)
        self.canvas.config(width=width, height=height)

        max_possible = width // 2
        num = min(128, max_possible)
        if num < 1:
            num = 1
        self._num_velocities = num
        self._build_bars(num, width, height)

    def _build_bars(self, num_bins, canvas_width, canvas_height):
        self.canvas.delete("all")
        self.rects = []
        self.start_times = [None] * num_bins
        self.active = set()

        # 2 Pixel Rand oben und unten
        top = 4
        bottom = canvas_height - 6
        if bottom <= top:
            top = 0
            bottom = canvas_height

        usable_width = canvas_width - 10
        step_width = usable_width / num_bins
        bar_width = max(1, step_width - 1)
        if bar_width < 1:
            bar_width = 1
            step_width = bar_width + 1

        for i in range(num_bins):
            x0 = 5 + i * step_width
            x1 = x0 + bar_width
            rect = self.canvas.create_rectangle(x0, top, x1, bottom,
                                                fill=self.bg_color, outline='')
            self.rects.append(rect)

    def set_queue(self, q):
        self.velocity_queue = q

    def _start_update_loop(self):
        self._update()
        self._after_id = self.after(50, self._start_update_loop)

    def _update(self):
        if self.velocity_queue is None:
            return

        current = time.perf_counter()

        while True:
            try:
                vel = self.velocity_queue.get_nowait()
            except queue.Empty:
                break

            if self._num_velocities == 128:
                idx = vel
            else:
                idx = int(vel * self._num_velocities / 128)
            if idx >= self._num_velocities:
                idx = self._num_velocities - 1

            self.start_times[idx] = current
            self.active.add(idx)

        to_remove = []
        for i in self.active:
            t0 = self.start_times[i]
            dt = current - t0

            if dt < WHITE_DURATION:
                color = '#FFFFFF'
            elif dt < WHITE_DURATION + DECAY_TIME:
                t = (dt - WHITE_DURATION) / DECAY_TIME
                # Interpolation von COLOR_VELOCITY_BAR zur Hintergrundfarbe
                r = int(self.fg_r + (self.bg_r - self.fg_r) * t)
                g = int(self.fg_g + (self.bg_g - self.fg_g) * t)
                b = int(self.fg_b + (self.bg_b - self.fg_b) * t)
                color = f'#{r:02x}{g:02x}{b:02x}'
            else:
                color = self.bg_color
                self.start_times[i] = None
                to_remove.append(i)

            self.canvas.itemconfig(self.rects[i], fill=color)

        for i in to_remove:
            self.active.discard(i)

    def destroy(self):
        if self._after_id:
            self.after_cancel(self._after_id)
        super().destroy()