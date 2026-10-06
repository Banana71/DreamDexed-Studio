# harvester/mixer_dialog.py
"""
MixerPanel – Read-only visualization of a DreamDexed performance's
mixer settings (TG levels, EQ/Comp flags, FX routing, master FX).
"""

import tkinter as tk
from harvester.constants import COLOR_BG, COLOR_FG, COLOR_FG_DIM


class MixerPanel(tk.Frame):
    """
    Displays the mixer tab of a performance (read-only).
    Expects pre-parsed data from the performance INI.
    """

    # --- Layout constants ---
    BOX_BG     = "#1e2e2a"
    FADE       = "#555555"
    FONT       = ("Segoe UI", 10)
    FONT_B     = ("Segoe UI", 10, "bold")
    LINE_COLOR = COLOR_FG_DIM

    ROW_HEIGHT = 34
    GAP        = 8
    X0         = 20
    Y0         = 20

    TG_NAME_W = 110
    VOL_W     = 50
    PAN_W     = 50
    EQ_W      = 55
    COMP_W    = 55
    FX1_W     = 50
    FX2_W     = 50

    FX_BLOCK_W = 160
    FX_BLOCK_H = 100
    MASTER_W   = 180
    MASTER_H   = 115

    def __init__(self, parent, tg_data, fx_slots, bus_params, master_fx_details):
        super().__init__(parent, bg=COLOR_BG)
        self.tg_data            = tg_data or {}
        self.fx_slots           = fx_slots or {}
        self.bus_params         = bus_params or {}
        # master_fx_details is accepted for API compatibility but not yet displayed.
        self.master_fx_details  = master_fx_details or {}
        self._build()

    # ------------------------------------------------------------------
    # Building
    # ------------------------------------------------------------------
    def _build(self):
        canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0)
        h_scroll = tk.Scrollbar(self, orient="horizontal",
                                command=canvas.xview, bg=COLOR_BG)
        v_scroll = tk.Scrollbar(self, orient="vertical",
                                command=canvas.yview, bg=COLOR_BG)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        canvas.bind("<Configure>",
                    lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # --- Column x positions ---
        x_tg   = self.X0
        x_vol  = x_tg   + self.TG_NAME_W + self.GAP
        x_pan  = x_vol  + self.VOL_W     + self.GAP
        x_eq   = x_pan  + self.PAN_W     + self.GAP
        x_comp = x_eq   + self.EQ_W      + self.GAP
        x_fx1  = x_comp + self.COMP_W    + self.GAP
        x_fx2  = x_fx1  + self.FX1_W     + self.GAP
        total_w = x_fx2 + self.FX2_W - self.X0

        # --- Row y positions ---
        header_y     = self.Y0
        line_y       = header_y + 18
        data_start_y = line_y + 10
        dry_y        = data_start_y + 8 * self.ROW_HEIGHT

        # --- Block 1 frame (TG 1..8 + Dry) ---
        canvas.create_rectangle(
            self.X0 - 6, header_y - 6,
            self.X0 + total_w + 6, dry_y + 18,
            outline=self.LINE_COLOR, width=1, fill=""
        )

        # --- Block 2 frame (FX section) ---
        block2_y      = dry_y + 40
        block2_bottom = block2_y + 2 * self.FX_BLOCK_H + 20 + 6
        canvas.create_rectangle(
            self.X0 - 6, block2_y - 6,
            self.X0 + total_w + 6, block2_bottom,
            outline=self.LINE_COLOR, width=1, fill=""
        )

        # --- Column headers ---
        headers = [
            (x_tg   + self.TG_NAME_W / 2, "TG"),
            (x_vol  + self.VOL_W     / 2, "Vol"),
            (x_pan  + self.PAN_W     / 2, "Pan"),
            (x_eq   + self.EQ_W      / 2, "EQ"),
            (x_comp + self.COMP_W    / 2, "Comp"),
            (x_fx1  + self.FX1_W     / 2, "FX1"),
            (x_fx2  + self.FX2_W     / 2, "FX2"),
        ]
        for x, text in headers:
            canvas.create_text(x, header_y, text=text, fill=COLOR_FG,
                               font=self.FONT_B, anchor="n")
        canvas.create_line(self.X0, line_y, self.X0 + total_w, line_y,
                           fill=self.LINE_COLOR)

        # --- TG rows 1..8 ---
        for tg in range(1, 9):
            data   = self.tg_data.get(tg, {})
            active = data.get('channel', 0) > 0
            fg     = COLOR_FG if active else self.FADE

            y = data_start_y + (tg - 1) * self.ROW_HEIGHT

            canvas.create_text(
                x_tg + self.TG_NAME_W / 2, y,
                text=f"TG{tg} {data.get('name', f'TG{tg}')[:10]}",
                fill=fg, font=self.FONT_B, anchor="n"
            )
            canvas.create_text(
                x_vol + self.VOL_W / 2, y,
                text=str(data.get('volume', 0)),
                fill=fg, font=self.FONT, anchor="n"
            )
            canvas.create_text(
                x_pan + self.PAN_W / 2, y,
                text=str(data.get('pan', 0)),
                fill=fg, font=self.FONT, anchor="n"
            )

            self._draw_flag_box(canvas, x_eq,   y, self.EQ_W,   "EQ",
                                data.get('eq_active', False))
            self._draw_flag_box(canvas, x_comp, y, self.COMP_W, "Comp",
                                data.get('comp_active', False))

            canvas.create_text(
                x_fx1 + self.FX1_W / 2, y,
                text=str(data.get('fx1send', 0)),
                fill=fg, font=self.FONT, anchor="n"
            )
            canvas.create_text(
                x_fx2 + self.FX2_W / 2, y,
                text=str(data.get('fx2send', 0)),
                fill=fg, font=self.FONT, anchor="n"
            )

        # --- Dry row (9th row) ---
        dry_val = self.bus_params.get('dry', '99')
        canvas.create_text(x_tg + self.TG_NAME_W / 2, dry_y, text="Dry",
                           fill=COLOR_FG, font=self.FONT_B, anchor="n")
        canvas.create_text(x_vol + self.VOL_W / 2, dry_y, text=str(dry_val),
                           fill=COLOR_FG, font=self.FONT, anchor="n")

        # --- FX1 block ---
        self._draw_fx_block(
            canvas,
            x=self.X0, y=block2_y,
            title="FX1",
            slot_prefix="FX1Slot",
            return_value=self.bus_params.get(
                'fx1_return',
                self.bus_params.get('reverb_level', '-')
            ),
        )

        # --- FX2 block ---
        self._draw_fx_block(
            canvas,
            x=self.X0, y=block2_y + self.FX_BLOCK_H + 20,
            title="FX2",
            slot_prefix="FX2Slot",
            return_value=self.bus_params.get('fx2_return', '-'),
        )

        # --- Master FX block (vertically centered next to the two FX blocks) ---
        master_x = self.X0 + self.FX_BLOCK_W + 50
        master_y = block2_y + (2 * self.FX_BLOCK_H + 20 - self.MASTER_H) / 2
        self._draw_fx_block(
            canvas,
            x=master_x, y=master_y,
            title="Master FX",
            slot_prefix="MasterFXSlot",
            return_value=None,
            width=self.MASTER_W,
            height=self.MASTER_H,
        )

    # ------------------------------------------------------------------
    # Drawing helpers
    # ------------------------------------------------------------------
    def _draw_flag_box(self, canvas, x, y, width, label, active):
        """Small status box (e.g. EQ / Comp on-off indicator)."""
        bg = self.BOX_BG if active else "#2a2a2a"
        fg = COLOR_FG   if active else self.FADE
        canvas.create_rectangle(x, y - 2, x + width, y + 16,
                                fill=bg, outline=self.LINE_COLOR)
        canvas.create_text(x + width / 2, y + 6, text=label,
                           fill=fg, font=self.FONT, anchor="center")

    def _draw_fx_block(self, canvas, x, y, title, slot_prefix,
                       return_value=None, width=None, height=None):
        """Renders a single FX block (title + up to 3 slots + optional return)."""
        w = width  if width  is not None else self.FX_BLOCK_W
        h = height if height is not None else self.FX_BLOCK_H

        canvas.create_rectangle(x, y, x + w, y + h,
                                fill=self.BOX_BG, outline=self.LINE_COLOR)
        canvas.create_text(x + 10, y + 14, text=title,
                           fill=COLOR_FG, font=self.FONT_B, anchor="w")

        for i in range(1, 4):
            slot = self.fx_slots.get(f"{slot_prefix}{i}", "-")
            if slot in (None, "", "None"):
                slot = "-"
            canvas.create_text(x + 15, y + 32 + (i - 1) * 18,
                               text=f"Slot{i}: {slot}",
                               fill=COLOR_FG, font=self.FONT, anchor="w")

        if return_value is not None:
            canvas.create_text(x + 15, y + h - 14,
                               text=f"Return: {return_value}",
                               fill=COLOR_FG, font=self.FONT, anchor="w")