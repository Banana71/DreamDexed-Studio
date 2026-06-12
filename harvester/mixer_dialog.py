# harvester/mixer_dialog.py
import tkinter as tk
from harvester.constants import COLOR_BG, COLOR_FG, COLOR_FG_DIM

class MixerPanel(tk.Frame):
    """
    Zeigt den Mixer‑Tab einer Performance an (rein lesend).
    Erwartet die bereits geparsten Daten aus der Performance‑INI.
    """
    def __init__(self, parent, tg_data, fx_slots, bus_params, master_fx_details):
        super().__init__(parent, bg=COLOR_BG)
        self.tg_data = tg_data
        self.fx_slots = fx_slots
        self.bus_params = bus_params
        self.master_fx_details = master_fx_details
        self._build()

    def _build(self):
        canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0)
        h_scroll = tk.Scrollbar(self, orient="horizontal", command=canvas.xview, bg=COLOR_BG)
        v_scroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview, bg=COLOR_BG)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        mixer_frame = tk.Frame(canvas, bg=COLOR_BG)
        canvas.create_window((0, 0), window=mixer_frame, anchor="nw")
        mixer_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        BOX_BG = "#1e2e2a"
        BOX_FG = COLOR_FG
        FADE = "#555555"
        LINE_COLOR = COLOR_FG_DIM
        FONT = ("Segoe UI", 10)
        FONT_B = ("Segoe UI", 10, "bold")

        x0 = 20
        y0 = 20
        row_h = 34
        gap = 8

        # Spaltenbreiten
        tg_name_w = 110
        vol_w = 50
        pan_w = 50
        eq_w = 55
        comp_w = 55
        fx1_w = 50
        fx2_w = 50

        # x-Koordinaten der Spaltenmitten (aufsummiert)
        x_tg = x0
        x_vol = x_tg + tg_name_w + gap
        x_pan = x_vol + vol_w + gap
        x_eq = x_pan + pan_w + gap
        x_comp = x_eq + eq_w + gap
        x_fx1 = x_comp + comp_w + gap
        x_fx2 = x_fx1 + fx1_w + gap

        total_w = x_fx2 + fx2_w - x0

        header_y = y0
        dry_y = y0 + 18 + 10 + 8 * row_h + 8

        # Rahmen Block 1
        block1_x1 = x0 - 6
        block1_y1 = header_y - 6
        block1_x2 = x0 + total_w + 6
        block1_y2 = dry_y + 18
        canvas.create_rectangle(block1_x1, block1_y1, block1_x2, block1_y2,
                                outline=LINE_COLOR, width=1, fill="")

        # Rahmen Block 2
        block2_y = dry_y + 40
        fx_block_w = 160
        fx_block_h = 100
        master_w = 180
        master_h = 115
        block2_x1 = x0 - 6
        block2_y1 = block2_y - 6
        block2_x2 = x0 + total_w + 6
        block2_y2 = block2_y + 2 * fx_block_h + 20 + 6
        canvas.create_rectangle(block2_x1, block2_y1, block2_x2, block2_y2,
                                outline=LINE_COLOR, width=1, fill="")

        # Überschriften
        canvas.create_text(x_tg + tg_name_w / 2, header_y, text="TG", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_vol + vol_w / 2, header_y, text="Vol", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_pan + pan_w / 2, header_y, text="Pan", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_eq + eq_w / 2, header_y, text="EQ", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_comp + comp_w / 2, header_y, text="Comp", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_fx1 + fx1_w / 2, header_y, text="FX1", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_fx2 + fx2_w / 2, header_y, text="FX2", fill=BOX_FG, font=FONT_B, anchor="n")

        line_y = header_y + 18
        canvas.create_line(x0, line_y, x0 + total_w, line_y, fill=LINE_COLOR)

        data_start_y = line_y + 10

        for tg in range(1, 9):
            data = self.tg_data.get(tg, {})
            ch = data.get('channel', 0)
            active = ch > 0
            fg = BOX_FG if active else FADE

            eq_active = data.get('eq_active', False)
            comp_active = data.get('comp_active', False)
            eq_bg = BOX_BG if eq_active else "#2a2a2a"
            eq_fg = BOX_FG if eq_active else FADE
            comp_bg = BOX_BG if comp_active else "#2a2a2a"
            comp_fg = BOX_FG if comp_active else FADE

            y = data_start_y + (tg - 1) * row_h

            name = data.get('name', f'TG{tg}')
            canvas.create_text(x_tg + tg_name_w / 2, y, text=f"TG{tg} {name[:10]}", fill=fg, font=FONT_B, anchor="n")

            # Vol & Pan getrennt
            vol = data.get('volume', 0)
            pan = data.get('pan', 0)
            canvas.create_text(x_vol + vol_w / 2, y, text=str(vol), fill=fg, font=FONT, anchor="n")
            canvas.create_text(x_pan + pan_w / 2, y, text=str(pan), fill=fg, font=FONT, anchor="n")

            # EQ-Box
            canvas.create_rectangle(x_eq, y - 2, x_eq + eq_w, y + 16,
                                    fill=eq_bg, outline=LINE_COLOR)
            canvas.create_text(x_eq + eq_w / 2, y + 6, text="EQ", fill=eq_fg, font=FONT, anchor="center")

            # Comp-Box
            canvas.create_rectangle(x_comp, y - 2, x_comp + comp_w, y + 16,
                                    fill=comp_bg, outline=LINE_COLOR)
            canvas.create_text(x_comp + comp_w / 2, y + 6, text="Comp", fill=comp_fg, font=FONT, anchor="center")

            # FX-Send-Werte
            fx1 = data.get('fx1send', 0)
            canvas.create_text(x_fx1 + fx1_w / 2, y, text=str(fx1), fill=fg, font=FONT, anchor="n")

            fx2 = data.get('fx2send', 0)
            canvas.create_text(x_fx2 + fx2_w / 2, y, text=str(fx2), fill=fg, font=FONT, anchor="n")

# harvester/mixer_dialog.py
import tkinter as tk
from harvester.constants import COLOR_BG, COLOR_FG, COLOR_FG_DIM

class MixerPanel(tk.Frame):
    """
    Zeigt den Mixer‑Tab einer Performance an (rein lesend).
    Erwartet die bereits geparsten Daten aus der Performance‑INI.
    """
    def __init__(self, parent, tg_data, fx_slots, bus_params, master_fx_details):
        super().__init__(parent, bg=COLOR_BG)
        self.tg_data = tg_data
        self.fx_slots = fx_slots
        self.bus_params = bus_params
        self.master_fx_details = master_fx_details
        self._build()

    def _build(self):
        canvas = tk.Canvas(self, bg=COLOR_BG, highlightthickness=0)
        h_scroll = tk.Scrollbar(self, orient="horizontal", command=canvas.xview, bg=COLOR_BG)
        v_scroll = tk.Scrollbar(self, orient="vertical", command=canvas.yview, bg=COLOR_BG)
        canvas.configure(xscrollcommand=h_scroll.set, yscrollcommand=v_scroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        h_scroll.grid(row=1, column=0, sticky="ew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        mixer_frame = tk.Frame(canvas, bg=COLOR_BG)
        canvas.create_window((0, 0), window=mixer_frame, anchor="nw")
        mixer_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        BOX_BG = "#1e2e2a"
        BOX_FG = COLOR_FG
        FADE = "#555555"
        LINE_COLOR = COLOR_FG_DIM
        FONT = ("Segoe UI", 10)
        FONT_B = ("Segoe UI", 10, "bold")

        x0 = 20
        y0 = 20
        row_h = 34
        gap = 8

        # Spaltenbreiten
        tg_name_w = 110
        vol_w = 50
        pan_w = 50
        eq_w = 55
        comp_w = 55
        fx1_w = 50
        fx2_w = 50

        # x-Koordinaten der Spaltenmitten (aufsummiert)
        x_tg = x0
        x_vol = x_tg + tg_name_w + gap
        x_pan = x_vol + vol_w + gap
        x_eq = x_pan + pan_w + gap
        x_comp = x_eq + eq_w + gap
        x_fx1 = x_comp + comp_w + gap
        x_fx2 = x_fx1 + fx1_w + gap

        total_w = x_fx2 + fx2_w - x0

        header_y = y0
        # dry_y ist die Y-Koordinate der 9. Zeile (Dry)
        dry_y = y0 + 18 + 10 + 8 * row_h + 8

        # Rahmen Block 1 (umfasst nun 9 Zeilen)
        block1_x1 = x0 - 6
        block1_y1 = header_y - 6
        block1_x2 = x0 + total_w + 6
        block1_y2 = dry_y + 18
        canvas.create_rectangle(block1_x1, block1_y1, block1_x2, block1_y2,
                                outline=LINE_COLOR, width=1, fill="")

        # Rahmen Block 2
        block2_y = dry_y + 40
        fx_block_w = 160
        fx_block_h = 100
        master_w = 180
        master_h = 115
        block2_x1 = x0 - 6
        block2_y1 = block2_y - 6
        block2_x2 = x0 + total_w + 6
        block2_y2 = block2_y + 2 * fx_block_h + 20 + 6
        canvas.create_rectangle(block2_x1, block2_y1, block2_x2, block2_y2,
                                outline=LINE_COLOR, width=1, fill="")

        # Überschriften
        canvas.create_text(x_tg + tg_name_w / 2, header_y, text="TG", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_vol + vol_w / 2, header_y, text="Vol", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_pan + pan_w / 2, header_y, text="Pan", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_eq + eq_w / 2, header_y, text="EQ", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_comp + comp_w / 2, header_y, text="Comp", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_fx1 + fx1_w / 2, header_y, text="FX1", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_fx2 + fx2_w / 2, header_y, text="FX2", fill=BOX_FG, font=FONT_B, anchor="n")

        line_y = header_y + 18
        canvas.create_line(x0, line_y, x0 + total_w, line_y, fill=LINE_COLOR)

        data_start_y = line_y + 10

        # TG-Zeilen 1..8
        for tg in range(1, 9):
            data = self.tg_data.get(tg, {})
            ch = data.get('channel', 0)
            active = ch > 0
            fg = BOX_FG if active else FADE

            eq_active = data.get('eq_active', False)
            comp_active = data.get('comp_active', False)
            eq_bg = BOX_BG if eq_active else "#2a2a2a"
            eq_fg = BOX_FG if eq_active else FADE
            comp_bg = BOX_BG if comp_active else "#2a2a2a"
            comp_fg = BOX_FG if comp_active else FADE

            y = data_start_y + (tg - 1) * row_h

            name = data.get('name', f'TG{tg}')
            canvas.create_text(x_tg + tg_name_w / 2, y, text=f"TG{tg} {name[:10]}", fill=fg, font=FONT_B, anchor="n")

            vol = data.get('volume', 0)
            pan = data.get('pan', 0)
            canvas.create_text(x_vol + vol_w / 2, y, text=str(vol), fill=fg, font=FONT, anchor="n")
            canvas.create_text(x_pan + pan_w / 2, y, text=str(pan), fill=fg, font=FONT, anchor="n")

            # EQ-Box
            canvas.create_rectangle(x_eq, y - 2, x_eq + eq_w, y + 16,
                                    fill=eq_bg, outline=LINE_COLOR)
            canvas.create_text(x_eq + eq_w / 2, y + 6, text="EQ", fill=eq_fg, font=FONT, anchor="center")

            # Comp-Box
            canvas.create_rectangle(x_comp, y - 2, x_comp + comp_w, y + 16,
                                    fill=comp_bg, outline=LINE_COLOR)
            canvas.create_text(x_comp + comp_w / 2, y + 6, text="Comp", fill=comp_fg, font=FONT, anchor="center")

            fx1 = data.get('fx1send', 0)
            canvas.create_text(x_fx1 + fx1_w / 2, y, text=str(fx1), fill=fg, font=FONT, anchor="n")

            fx2 = data.get('fx2send', 0)
            canvas.create_text(x_fx2 + fx2_w / 2, y, text=str(fx2), fill=fg, font=FONT, anchor="n")

        # Dry-Zeile (9. Zeile)
        dry_y = data_start_y + 8 * row_h
        dry = self.bus_params.get('dry', '99')
        canvas.create_text(x_tg + tg_name_w /2, dry_y, text="Dry           ", fill=BOX_FG, font=FONT_B, anchor="n")
        canvas.create_text(x_vol + vol_w / 2, dry_y, text=str(dry), fill=BOX_FG, font=FONT, anchor="n")

        # FX1-Block
        fx1_x = x0
        fx1_y = block2_y
        canvas.create_rectangle(fx1_x, fx1_y, fx1_x + fx_block_w, fx1_y + fx_block_h, fill=BOX_BG, outline=LINE_COLOR)
        for i in range(1, 4):
            slot = self.fx_slots.get(f"FX1Slot{i}", "-")
            if slot == "None": slot = "-"
            canvas.create_text(fx1_x + 15, fx1_y + 32 + (i - 1) * 18, text=f"Slot{i}: {slot}", fill=BOX_FG, font=FONT, anchor="w")
        ret1 = self.bus_params.get('fx1_return', self.bus_params.get('reverb_level', '-'))
        canvas.create_text(fx1_x + 15, fx1_y + fx_block_h - 14, text=f"Return: {ret1}", fill=BOX_FG, font=FONT, anchor="w")

        # FX2-Block
        fx2_x = x0
        fx2_y = fx1_y + fx_block_h + 20
        canvas.create_rectangle(fx2_x, fx2_y, fx2_x + fx_block_w, fx2_y + fx_block_h, fill=BOX_BG, outline=LINE_COLOR)
        for i in range(1, 4):
            slot = self.fx_slots.get(f"FX2Slot{i}", "-")
            if slot == "None": slot = "-"
            canvas.create_text(fx2_x + 15, fx2_y + 32 + (i - 1) * 18, text=f"Slot{i}: {slot}", fill=BOX_FG, font=FONT, anchor="w")
        ret2 = self.bus_params.get('fx2_return', '-')
        canvas.create_text(fx2_x + 15, fx2_y + fx_block_h - 14, text=f"Return: {ret2}", fill=BOX_FG, font=FONT, anchor="w")

        # Master-FX-Block
        master_x = fx2_x + fx_block_w + 50
        master_y = block2_y + (2 * fx_block_h + 20 - master_h) / 2
        canvas.create_rectangle(master_x, master_y, master_x + master_w, master_y + master_h, fill=BOX_BG, outline=LINE_COLOR)
        for i in range(1, 4):
            slot = self.fx_slots.get(f"MasterFXSlot{i}", "-")
            if slot == "None": slot = "-"
            canvas.create_text(master_x + 15, master_y + 42 + (i - 1) * 18, text=f"Slot{i}: {slot}", fill=BOX_FG, font=FONT, anchor="w")
        # FX1-Block
        fx1_x = x0
        fx1_y = block2_y
        canvas.create_rectangle(fx1_x, fx1_y, fx1_x + fx_block_w, fx1_y + fx_block_h, fill=BOX_BG, outline=LINE_COLOR)
        canvas.create_text(fx1_x + 10, fx1_y + 14, text="FX1", fill=BOX_FG, font=FONT_B, anchor="w")
        for i in range(1, 4):
            slot = self.fx_slots.get(f"FX1Slot{i}", "-")
            if slot == "None": slot = "-"
            canvas.create_text(fx1_x + 15, fx1_y + 32 + (i - 1) * 18, text=f"Slot{i}: {slot}", fill=BOX_FG, font=FONT, anchor="w")
        ret1 = self.bus_params.get('fx1_return', self.bus_params.get('reverb_level', '-'))
        canvas.create_text(fx1_x + 15, fx1_y + fx_block_h - 14, text=f"Return: {ret1}", fill=BOX_FG, font=FONT, anchor="w")

        # FX2-Block
        fx2_x = x0
        fx2_y = fx1_y + fx_block_h + 20
        canvas.create_rectangle(fx2_x, fx2_y, fx2_x + fx_block_w, fx2_y + fx_block_h, fill=BOX_BG, outline=LINE_COLOR)
        canvas.create_text(fx2_x + 10, fx2_y + 14, text="FX2", fill=BOX_FG, font=FONT_B, anchor="w")
        for i in range(1, 4):
            slot = self.fx_slots.get(f"FX2Slot{i}", "-")
            if slot == "None": slot = "-"
            canvas.create_text(fx2_x + 15, fx2_y + 32 + (i - 1) * 18, text=f"Slot{i}: {slot}", fill=BOX_FG, font=FONT, anchor="w")
        ret2 = self.bus_params.get('fx2_return', '-')
        canvas.create_text(fx2_x + 15, fx2_y + fx_block_h - 14, text=f"Return: {ret2}", fill=BOX_FG, font=FONT, anchor="w")

        # Master-FX-Block
        master_x = fx2_x + fx_block_w + 50
        master_y = block2_y + (2 * fx_block_h + 20 - master_h) / 2
        canvas.create_rectangle(master_x, master_y, master_x + master_w, master_y + master_h, fill=BOX_BG, outline=LINE_COLOR)
        canvas.create_text(master_x + 10, master_y + 14, text="Master FX", fill=BOX_FG, font=FONT_B, anchor="w")
        for i in range(1, 4):
            slot = self.fx_slots.get(f"MasterFXSlot{i}", "-")
            if slot == "None": slot = "-"
            canvas.create_text(master_x + 15, master_y + 42 + (i - 1) * 18, text=f"Slot{i}: {slot}", fill=BOX_FG, font=FONT, anchor="w")