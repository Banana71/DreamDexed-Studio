# harvester/rename_dialog.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import ftplib
import threading
import io
import re
import os

from harvester.constants import *
from harvester.ini_utils import hex_to_text, text_to_hex, parse_ini_for_voices, rebuild_ini_line
from .perf2sheet import parse_voice_155, generate_datasheet, sanitize_filename
from .Perf2syx import single_to_bank128, yamaha_checksum, INIT_VOICE_128, SYX_HDR, SYX_TAIL
from .mixer_dialog import MixerPanel

class RenameDialog(tk.Toplevel):
    def __init__(self, parent, ftp_creds, remote_dir, filename, refresh_callback, harvester):
        super().__init__(parent)
        self.harvester = harvester
        self.parent = parent
        self.ftp_creds = ftp_creds
        self.remote_dir = remote_dir
        self.filename = filename
        self.refresh_callback = refresh_callback
        self.title(f"{self.harvester.get_current_profile_name()} Performance editor: {filename}")

        scale = self.harvester.scale
        w = int(660 * scale)
        h = int(740 * scale)
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        parent_x = self.parent.winfo_rootx()
        parent_y = self.parent.winfo_rooty()
        parent_w = self.parent.winfo_width()
        parent_h = self.parent.winfo_height()
        x = parent_x + (parent_w // 2) - (w // 2) +6
        y = parent_y + (parent_h // 2) - (h // 2) +14
        self.geometry(f"+{x}+{y}")
        self.grab_set()
        self.configure(bg=COLOR_BG)

        base = re.sub(r"^\d+_", "", filename.replace(".ini", ""))
        self.perf_name = base

        self.watermark1 = harvester.get_watermark1()
        self.watermark2 = harvester.get_watermark2()

        self.ini_lines = None
        self.tg_data = None
        self.fx_slots = None
        self.bus_params = {}
        self.master_fx_details = {}

        self.name_entries = {}
        self.entry_ch = {}
        self.entry_vol = {}
        self.entry_pan = {}
        self.entry_fx1 = {}
        self.entry_fx2 = {}
        self.entry_detune = {}
        self.entry_cutoff = {}
        self.entry_res = {}
        self.entry_notelow = {}
        self.entry_notehigh = {}
        self.entry_tglink = {}
        self.load_remote_file()

    # -----------------------------------------------------------------
    # Laden & Parsen (unverändert)
    # -----------------------------------------------------------------
    def load_remote_file(self):
        def task():
            ftp = None
            try:
                ftp = ftplib.FTP(self.ftp_creds["ip"], timeout=10)
                ftp.login(self.ftp_creds["user"], self.ftp_creds["password"])
                ftp.cwd(self.remote_dir)
                buf = io.BytesIO()
                ftp.retrbinary(f"RETR {self.filename}", buf.write)
                content = buf.getvalue().decode('utf-8', errors='replace')
                lines = content.splitlines(keepends=True)
                self.after(0, lambda: self.on_file_loaded(lines))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Failed to load file:\n{e}"))
                self.after(0, self.destroy)
            finally:
                if ftp:
                    try:
                        ftp.close()
                    except:
                        pass
        threading.Thread(target=task, daemon=True).start()

    def parse_all_parameters(self, lines):
        tg_data = {tg: {} for tg in range(1, 9)}
        fx_slots = {}
        reverb_enable = False
        compressor_enable = False
        bus_params = {}
        master_fx_details = {}

        for line in lines:
            line = line.strip()
            if not line or '=' not in line:
                continue
            key, value = line.split('=', 1)

            if key == "ReverbEnable":
                reverb_enable = (value.strip() == "1")
                continue
            if key == "CompressorEnable":
                compressor_enable = (value.strip() == "1")
                continue

            # EQ- und Compressor-Parameter pro TG einsammeln
            for tg in range(1, 9):
                if key == f"CompressorEnable{tg}":
                    tg_data[tg]['comp_enable'] = int(value)
                elif key == f"EQLow{tg}":
                    tg_data[tg].setdefault('eq_params', {})['low'] = int(value)
                elif key == f"EQMid{tg}":
                    tg_data[tg].setdefault('eq_params', {})['mid'] = int(value)
                elif key == f"EQHigh{tg}":
                    tg_data[tg].setdefault('eq_params', {})['high'] = int(value)
                elif key == f"EQGain{tg}":
                    tg_data[tg].setdefault('eq_params', {})['gain'] = int(value)
                elif key == f"EQPreLowcut{tg}":
                    tg_data[tg].setdefault('eq_params', {})['pre_lowcut'] = int(value)
                elif key == f"EQPreHighcut{tg}":
                    tg_data[tg].setdefault('eq_params', {})['pre_highcut'] = int(value)

            for tg in range(1, 9):
                if key == f"VoiceData{tg}":
                    tg_data[tg]['hex'] = value
                elif key == f"MIDIChannel{tg}":
                    tg_data[tg]['channel'] = int(value)
                elif key == f"Volume{tg}":
                    tg_data[tg]['volume'] = int(value)
                elif key == f"Pan{tg}":
                    tg_data[tg]['pan'] = int(value)
                elif key == f"FX1Send{tg}":
                    tg_data[tg]['fx1send'] = int(value)
                elif key == f"FX2Send{tg}":
                    tg_data[tg]['fx2send'] = int(value)
                elif key == f"NoteLimitLow{tg}":
                    tg_data[tg]['notelow'] = int(value)
                elif key == f"NoteLimitHigh{tg}":
                    tg_data[tg]['notehigh'] = int(value)
                elif key == f"TGLink{tg}":
                    tg_data[tg]['tglink'] = int(value)
                elif key == f"BankNumber{tg}":
                    tg_data[tg]['bank'] = int(value)
                elif key == f"VoiceNumber{tg}":
                    tg_data[tg]['voice'] = int(value)
                elif key == f"Detune{tg}":
                    tg_data[tg]['detune'] = int(value)
                elif key == f"Cutoff{tg}":
                    tg_data[tg]['cutoff'] = int(value)
                elif key == f"Resonance{tg}":
                    tg_data[tg]['resonance'] = int(value)

            if key.startswith("Bus1SendFX1Slot"):
                slot = key.replace("Bus1Send", "")
                fx_slots[slot] = value
            elif key.startswith("Bus1SendFX2Slot"):
                slot = key.replace("Bus1Send", "")
                fx_slots[slot] = value
            elif key.startswith("Out1MasterFXSlot"):
                slot = key.replace("Out1", "")
                fx_slots[slot] = value

            if key == "Bus1MixerDryLevel":
                bus_params['dry'] = value
            elif key == "Bus1ReturnLevel":
                bus_params['return'] = value
            elif key == "Bus1FXBypass":
                bus_params['bypass'] = value
            elif key == "Bus1SendFX1ReturnLevel":
                bus_params['fx1_return'] = value
            elif key == "Bus1SendFX2ReturnLevel":
                bus_params['fx2_return'] = value
            if key == "ReverbLevel":
                bus_params['reverb_level'] = value

            for fx in ["EQ", "Compressor", "PlateReverb"]:
                if key.startswith(f"Out1MasterFX{fx}") and ("Mix" in key or "Bypass" in key):
                    master_fx_details[key] = value

        if reverb_enable and not fx_slots.get("FX1Slot1"):
            fx_slots["FX1Slot1"] = "PlateReverb"
        if compressor_enable and not fx_slots.get("MasterFXSlot1"):
            fx_slots["MasterFXSlot1"] = "Compressor"

        for tg in range(1, 9):
            if tg in tg_data and 'hex' in tg_data[tg]:
                tg_data[tg]['name'] = hex_to_text(tg_data[tg]['hex'])
            else:
                if tg not in tg_data:
                    tg_data[tg] = {}
                if 'name' not in tg_data[tg]:
                    tg_data[tg]['name'] = f"TG{tg}"

        # Flags für EQ und Compressor berechnen
        for tg in range(1, 9):
            ch = tg_data[tg].get('channel', 0)
            eq_params = tg_data[tg].get('eq_params', {})
            if ch > 0 and eq_params:
                defaults = {'low': 0, 'mid': 0, 'high': 0, 'gain': 0, 'pre_lowcut': 0, 'pre_highcut': 60}
                eq_active = any(
                    eq_params.get(k) is not None and eq_params.get(k) != defaults[k]
                    for k in defaults
                )
            else:
                eq_active = False
            tg_data[tg]['eq_active'] = eq_active

            comp_enable = tg_data[tg].get('comp_enable', 0)
            tg_data[tg]['comp_active'] = (ch > 0 and comp_enable == 1)

        return tg_data, fx_slots, bus_params, master_fx_details

    def on_file_loaded(self, lines):
        try:
            self.ini_lines = lines
            self.tg_data, self.fx_slots, self.bus_params, self.master_fx_details = self.parse_all_parameters(lines)
            self.build_gui()
        except Exception as e:
            import traceback
            self.harvester.log_message(traceback.format_exc())

    def build_gui(self):
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)

        editor_frame = tk.Frame(nb, bg=COLOR_BG)
        nb.add(editor_frame, text="TG‑Editor")
        self._build_editor_tab(editor_frame)

        mixer_frame = MixerPanel(nb, self.tg_data, self.fx_slots,
                                self.bus_params, self.master_fx_details)
        nb.add(mixer_frame, text="Mixer")
    # -----------------------------------------------------------------
    # TG‑Editor Tab (unverändert)
    # -----------------------------------------------------------------
    def _build_editor_tab(self, parent):
        canvas = tk.Canvas(parent, bg=COLOR_BG, highlightthickness=0)
        scrollbar = tk.Scrollbar(parent, orient="vertical", command=canvas.yview, bg=COLOR_BG)
        scrollable_frame = tk.Frame(canvas, bg=COLOR_BG)
        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        lbl_style = {"bg": COLOR_BG, "fg": COLOR_FG, "font": FONT_NORMAL}
        entry_style = {"bg": COLOR_BG_ENTRY, "fg": COLOR_FG, "font": FONT_NORMAL,
                       "insertbackground": COLOR_FG, "relief": "solid", "borderwidth": 1,
                       "highlightcolor": COLOR_BG_SELECT, "highlightbackground": COLOR_BG_SELECT,
                       "highlightthickness": 1}
        btn_style = {"font": FONT_NORMAL, "bg": COLOR_BG_BUTTON, "fg": COLOR_FG,
                     "activebackground": COLOR_BG_SELECT, "activeforeground": COLOR_FG,
                     "relief": "raised", "cursor": "hand2"}

        top_frame = tk.Frame(scrollable_frame, bg=COLOR_BG)
        top_frame.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(top_frame, text="Performance-Name:", **lbl_style).grid(row=0, column=0, sticky="w", padx=(0,5))
        self.entry_perf_name = tk.Entry(top_frame, width=15, **entry_style)
        self.entry_perf_name.insert(0, self.perf_name)
        self.entry_perf_name.grid(row=0, column=1, sticky="w", padx=(0,20))

        tk.Label(top_frame, text="Watermark 1:", **lbl_style).grid(row=1, column=0, sticky="w", padx=(0,5))
        self.entry_wm1 = tk.Label(top_frame, width=14, bg=COLOR_BG_ENTRY, fg=COLOR_FG,
                                  text=self.watermark1, anchor="w", relief="sunken", padx=5, pady=2, font=FONT_NORMAL)
        self.entry_wm1.grid(row=1, column=1, sticky="w", padx=(0,20))

        tk.Label(top_frame, text="Watermark 2:", **lbl_style).grid(row=2, column=0, sticky="w", padx=(0,5))
        self.entry_wm2 = tk.Label(top_frame, width=14, bg=COLOR_BG_ENTRY, fg=COLOR_FG,
                                  text=self.watermark2, anchor="w", relief="sunken", padx=5, pady=2, font=FONT_NORMAL)
        self.entry_wm2.grid(row=2, column=1, sticky="w", padx=(0,20))

        apply_btn_style = btn_style.copy()
        apply_btn_style['height'] = 1
        apply_btn_style['pady'] = 0
        btn_apply = tk.Button(top_frame, text="set watermarks", width=13,
                              command=self.apply_watermarks_to_inactive, **apply_btn_style)
        btn_apply.grid(row=2, column=2, sticky="w", padx=5)
        dexed_path = self.harvester.entry_dexed_path.get().strip()
        if dexed_path:
            btn_temp_syx = tk.Button(top_frame, text="set Temp.syx", width=13,
                                     command=self.export_temp_syx, **apply_btn_style)
            btn_temp_syx.grid(row=2, column=3, sticky="w", padx=5)

        sep = tk.Frame(scrollable_frame, height=2, bg=COLOR_FG)
        sep.pack(fill="x", padx=10, pady=10)

        table_frame = tk.Frame(scrollable_frame, bg=COLOR_BG)
        table_frame.pack(fill="x", padx=10)

        col_widths = {
            0: 3, 1: 11, 2: 6, 3: 3, 4: 3, 5: 4, 6: 4, 7: 4,
            8: 4, 9: 4, 10: 4, 11: 4, 12: 4, 13: 4, 14: 6
        }
        for col, w in col_widths.items():
            table_frame.grid_columnconfigure(col, weight=0)

        headers = ["", "Name", "Bank/\nVoice", "Ch", "Vol", "PAN", "FX1\nSend", "FX2\nSend",
                   "Det.", "Cutoff", "Res.", "Note\nLow", "Note\nHigh", "TG\nLink", "Sheet"]
        for col, text in enumerate(headers):
            if text == "": continue
            lbl = tk.Label(table_frame, text=text, **lbl_style, anchor="center", justify="center",
                           width=col_widths.get(col, 6))
            lbl.grid(row=0, column=col, padx=1, pady=1, sticky="nsew")

        for tg in range(1, 9):
            data = self.tg_data.get(tg, {})
            ch = data.get('channel', 0)
            row = tg

            tk.Label(table_frame, text=f"TG{tg}", **lbl_style, anchor="center",
                     width=col_widths[0]).grid(row=row, column=0, padx=1, pady=1)

            entry_name = tk.Entry(table_frame, width=col_widths[1], **entry_style)
            entry_name.insert(0, data.get('name', f"TG{tg}"))
            entry_name.grid(row=row, column=1, padx=1, pady=1, sticky="w")
            self.name_entries[tg] = entry_name

            bank = data.get('bank', 0)
            voice = data.get('voice', 0)
            bank_voice_text = f"{bank + 1:03d}:{voice:02d}" if ch > 0 else "---:--"
            lbl_bv = tk.Label(table_frame, text=bank_voice_text, **lbl_style, anchor="center", width=col_widths[2])
            lbl_bv.grid(row=row, column=2, padx=1, pady=1)

            placeholder = "-" if ch == 0 else ""

            entry_ch = tk.Entry(table_frame, width=col_widths[3], **entry_style)
            entry_ch.insert(0, str(ch) if ch > 0 else placeholder)
            entry_ch.grid(row=row, column=3, padx=1, pady=1)
            self.entry_ch[tg] = entry_ch

            entry_vol = tk.Entry(table_frame, width=col_widths[4], **entry_style)
            entry_vol.insert(0, str(data.get('volume', 0)) if ch > 0 else placeholder)
            entry_vol.grid(row=row, column=4, padx=1, pady=1)
            self.entry_vol[tg] = entry_vol

            entry_pan = tk.Entry(table_frame, width=col_widths[5], **entry_style)
            entry_pan.insert(0, str(data.get('pan', 0)) if ch > 0 else placeholder)
            entry_pan.grid(row=row, column=5, padx=1, pady=1)
            self.entry_pan[tg] = entry_pan

            entry_fx1 = tk.Entry(table_frame, width=col_widths[6], **entry_style)
            entry_fx1.insert(0, str(data.get('fx1send', 0)) if ch > 0 else placeholder)
            entry_fx1.grid(row=row, column=6, padx=1, pady=1)
            self.entry_fx1[tg] = entry_fx1

            entry_fx2 = tk.Entry(table_frame, width=col_widths[7], **entry_style)
            entry_fx2.insert(0, str(data.get('fx2send', 0)) if ch > 0 else placeholder)
            entry_fx2.grid(row=row, column=7, padx=1, pady=1)
            self.entry_fx2[tg] = entry_fx2

            entry_detune = tk.Entry(table_frame, width=col_widths[8], **entry_style)
            entry_detune.insert(0, str(data.get('detune', 0)) if ch > 0 else placeholder)
            entry_detune.grid(row=row, column=8, padx=1, pady=1)
            self.entry_detune[tg] = entry_detune

            entry_cutoff = tk.Entry(table_frame, width=col_widths[9], **entry_style)
            entry_cutoff.insert(0, str(data.get('cutoff', 99)) if ch > 0 else placeholder)
            entry_cutoff.grid(row=row, column=9, padx=1, pady=1)
            self.entry_cutoff[tg] = entry_cutoff

            entry_res = tk.Entry(table_frame, width=col_widths[10], **entry_style)
            entry_res.insert(0, str(data.get('resonance', 0)) if ch > 0 else placeholder)
            entry_res.grid(row=row, column=10, padx=1, pady=1)
            self.entry_res[tg] = entry_res

            entry_notelow = tk.Entry(table_frame, width=col_widths[11], **entry_style)
            entry_notelow.insert(0, str(data.get('notelow', 0)) if ch > 0 else placeholder)
            entry_notelow.grid(row=row, column=11, padx=1, pady=1)
            self.entry_notelow[tg] = entry_notelow

            entry_notehigh = tk.Entry(table_frame, width=col_widths[12], **entry_style)
            entry_notehigh.insert(0, str(data.get('notehigh', 127)) if ch > 0 else placeholder)
            entry_notehigh.grid(row=row, column=12, padx=1, pady=1)
            self.entry_notehigh[tg] = entry_notehigh

            tglink_val = data.get('tglink', 0)
            if ch == 0: tglink_display = "-"
            else:
                if tglink_val == 0: tglink_display = "-"
                elif 1 <= tglink_val <= 4: tglink_display = chr(ord('A') + tglink_val - 1)
                else: tglink_display = str(tglink_val)
            entry_tglink = tk.Entry(table_frame, width=col_widths[13], **entry_style)
            entry_tglink.insert(0, tglink_display)
            entry_tglink.grid(row=row, column=13, padx=1, pady=1)
            self.entry_tglink[tg] = entry_tglink

            sheet_lbl = tk.Label(table_frame, text="🗒️", bg=COLOR_BG, fg=COLOR_FG,
                                 font=("Segoe UI Emoji", int(11 * self.harvester.scale)),
                                 anchor="center", width=col_widths[14], cursor="hand2")
            sheet_lbl.grid(row=row, column=14, padx=2, pady=1)
            sheet_lbl.bind("<Button-1>", lambda e, t=tg: self.on_sheet_click(t))

        sep3 = tk.Frame(scrollable_frame, height=2, bg=COLOR_FG)
        sep3.pack(fill="x", padx=10, pady=10)
        btn_frame = tk.Frame(scrollable_frame, bg=COLOR_BG)
        btn_frame.pack(pady=20)
        btn_save = tk.Button(btn_frame, text=" Save ", command=self.save_changes, **btn_style)
        btn_save.pack(side="left", padx=5)
        btn_cancel = tk.Button(btn_frame, text="Cancel", command=self.destroy, **btn_style)
        btn_cancel.pack(side="left", padx=5)

    def on_sheet_click(self, tg):
        hex_str = self.tg_data.get(tg, {}).get('hex', '')
        if not hex_str:
            self.harvester.log_message(f"❌ TG{tg}: No VoiceData available.")
            return

        try:
            hex_bytes = [int(b, 16) for b in hex_str.split()]
            voice_bytes = bytes(hex_bytes)
            if len(voice_bytes) not in (155, 156):
                raise ValueError(f"Invalid length: {len(voice_bytes)} bytes")
        except Exception as e:
            self.harvester.log_message(f"❌ TG{tg}: Error parsing VoiceData: {e}")
            return

        try:
            params = parse_voice_155(voice_bytes)

            bank_num = None
            bank_dir = os.path.basename(self.remote_dir)
            match_bank = re.match(r'^(\d+)_', bank_dir)
            if match_bank:
                bank_num = int(match_bank.group(1))

            perf_num = None
            perf_name_clean = None
            match_perf = re.match(r'^(\d+)_(.*)\.ini$', self.filename, re.IGNORECASE)
            if match_perf:
                perf_num = int(match_perf.group(1))
                perf_name_clean = match_perf.group(2)

            if bank_num is None or perf_num is None:
                bank_name_display = self.entry_perf_name.get().strip()
                if not bank_name_display:
                    bank_name_display = "Unnamed"
                sheet_text = generate_datasheet(params, bank_name_display, tg)
            else:
                sheet_text = generate_datasheet(params, "", tg,
                                                bank_num=bank_num,
                                                perf_num=perf_num,
                                                perf_name=perf_name_clean)
        except Exception as e:
            self.harvester.log_message(f"❌ TG{tg}: Error generating datasheet: {e}")
            return

        base = self.harvester.entry_base_path.get()
        sheet_dir = os.path.join(base, "VoiceSheets")
        os.makedirs(sheet_dir, exist_ok=True)
        safe_name = sanitize_filename(params['name'])
        filename = f"{safe_name}.txt"
        filepath = os.path.join(sheet_dir, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(sheet_text)
            self.harvester.log_message(f"✅ Datasheet saved: {filepath}")
        except Exception as e:
            self.harvester.log_message(f"❌ Error saving file: {e}")

        self.show_sheet_window(sheet_text, filename)

    def show_sheet_window(self, sheet_text, filename):
        win = tk.Toplevel(self)
        win.title(f"DX7 Voice Data Sheet - {filename}")
        win.geometry("600x800")
        win.configure(bg=COLOR_BG)

        text_widget = scrolledtext.ScrolledText(win, wrap=tk.NONE, font=("Courier New", 10),
                                                bg=COLOR_BG, fg=COLOR_FG,
                                                insertbackground=COLOR_FG)
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, sheet_text)
        text_widget.config(state=tk.DISABLED)

        btn_close = tk.Button(win, text="Close", command=win.destroy,
                              bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                              activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
                              font=FONT_NORMAL, relief="raised", cursor="hand2")
        btn_close.pack(pady=10)

    def export_temp_syx(self):
        dexed_path = self.harvester.entry_dexed_path.get().strip()
        if not dexed_path:
            self.harvester.log_message("❌ Dexed path is not set. Cannot export temp.syx.")
            return

        perf_name = self.entry_perf_name.get().strip()[:10].ljust(10)

        voices_128 = []
        for tg in range(1, 9):
            data = self.tg_data.get(tg, {})
            if data.get('channel', 0) == 0:
                continue

            hex_str = data.get('hex', '')
            if not hex_str:
                continue

            try:
                parts = [t for t in re.split(r'[\s,;]+', hex_str.strip()) if t]
                voice_bytes = bytes([int(p, 16) for p in parts])
            except Exception:
                self.harvester.log_message(f"❌ Invalid VoiceData for TG{tg} – skipped.")
                continue

            bankv = single_to_bank128(voice_bytes, perf_name)
            if bankv is None:
                self.harvester.log_message(f"❌ Could not convert TG{tg} voice to bank format.")
                continue
            voices_128.append(bankv)

        if not voices_128:
            self.harvester.log_message("⚠️ No active voices found. Temp.syx not created.")
            return

        while len(voices_128) < 32:
            voices_128.append(INIT_VOICE_128)

        bank_data = b''.join(voices_128)
        chk = yamaha_checksum(bank_data)
        syx = SYX_HDR + bank_data + bytes([chk, SYX_TAIL])

        temp_dir = os.path.join(dexed_path, "Temp")
        try:
            os.makedirs(temp_dir, exist_ok=True)
            filepath = os.path.join(temp_dir, "temp.syx")
            with open(filepath, 'wb') as f:
                f.write(syx)
            self.harvester.log_message(f"✅ temp.syx saved to {filepath}")
        except Exception as e:
            self.harvester.log_message(f"❌ Failed to write temp.syx: {e}")

    def apply_watermarks_to_inactive(self):
        wm1 = self.watermark1[:10]
        wm2 = self.watermark2[:10]
        watermarks = [wm1, wm2]
        idx = 0
        for tg in range(1, 9):
            if self.tg_data.get(tg, {}).get('channel', 0) == 0:
                if idx < len(watermarks):
                    new_name = watermarks[idx]
                else:
                    new_name = f"TG{tg}"
                self.name_entries[tg].delete(0, tk.END)
                self.name_entries[tg].insert(0, new_name)
                idx += 1

    def save_changes(self):
        new_perf_name = self.entry_perf_name.get().strip()
        if not new_perf_name:
            new_perf_name = "Unnamed"

        old_channels = {tg: self.tg_data.get(tg, {}).get('channel', 0) for tg in range(1,9)}

        new_params = {}
        for tg in range(1, 9):
            new_name = self.name_entries[tg].get().strip()
            if not new_name:
                new_name = " " * 10
            new_hex = text_to_hex(new_name)
            new_params[tg] = {'hex': new_hex}

            ch_str = self.entry_ch[tg].get().strip()
            if ch_str and ch_str != "-":
                try:
                    new_params[tg]['channel'] = int(ch_str)
                except ValueError:
                    new_params[tg]['channel'] = 0
            else:
                new_params[tg]['channel'] = 0

            for attr, entry_dict, default in [
                ('volume', self.entry_vol, 0),
                ('pan', self.entry_pan, 0),
                ('fx1send', self.entry_fx1, 0),
                ('fx2send', self.entry_fx2, 0),
                ('detune', self.entry_detune, 0),
                ('cutoff', self.entry_cutoff, 99),
                ('resonance', self.entry_res, 0),
                ('notelow', self.entry_notelow, 0),
                ('notehigh', self.entry_notehigh, 127)
            ]:
                val_str = entry_dict[tg].get().strip()
                if val_str and val_str != '-':
                    try:
                        new_params[tg][attr] = int(val_str)
                    except ValueError:
                        new_params[tg][attr] = default
                else:
                    new_params[tg][attr] = default

            tglink_str = self.entry_tglink[tg].get().strip().upper()
            if tglink_str == 'A':
                tglink_val = 1
            elif tglink_str == 'B':
                tglink_val = 2
            elif tglink_str == 'C':
                tglink_val = 3
            elif tglink_str == 'D':
                tglink_val = 4
            elif tglink_str in ('-', ''):
                tglink_val = 0
            else:
                try:
                    tglink_val = int(tglink_str)
                except ValueError:
                    tglink_val = 0
            new_params[tg]['tglink'] = tglink_val

        new_lines = []
        for line in self.ini_lines:
            original_line = line
            found = False
            for tg in range(1, 9):
                key_voice = f"VoiceData{tg}"
                if line.startswith(key_voice + "="):
                    new_hex = new_params[tg]['hex']
                    new_line = rebuild_ini_line(line, new_hex)
                    new_lines.append(new_line)
                    found = True
                    break
                for attr, key_pattern in [
                    ('channel', f"MIDIChannel{tg}"),
                    ('volume', f"Volume{tg}"),
                    ('pan', f"Pan{tg}"),
                    ('fx1send', f"FX1Send{tg}"),
                    ('fx2send', f"FX2Send{tg}"),
                    ('detune', f"Detune{tg}"),
                    ('cutoff', f"Cutoff{tg}"),
                    ('resonance', f"Resonance{tg}"),
                    ('notelow', f"NoteLimitLow{tg}"),
                    ('notehigh', f"NoteLimitHigh{tg}"),
                    ('tglink', f"TGLink{tg}")
                ]:
                    if line.startswith(key_pattern + "="):
                        val = new_params[tg].get(attr)
                        if val is not None:
                            new_lines.append(f"{key_pattern}={val}\n")
                        else:
                            new_lines.append(original_line)
                        found = True
                        break
            if not found:
                new_lines.append(original_line)

        def upload_and_rename():
            ftp = None
            try:
                ftp = ftplib.FTP(self.ftp_creds["ip"], timeout=10)
                ftp.login(self.ftp_creds["user"], self.ftp_creds["password"])
                ftp.cwd(self.remote_dir)
                buf = io.BytesIO()
                buf.write(''.join(new_lines).encode('utf-8'))
                buf.seek(0)
                ftp.storbinary(f"STOR {self.filename}", buf)
                self.harvester.log_message(f"📤 File '{self.filename}' saved (parameters updated).")
                new_filename = self.filename
                old_base = self.filename.replace(".ini", "")
                if "_" in old_base:
                    old_perf_name = old_base.split("_", 1)[1]
                else:
                    old_perf_name = old_base
                if new_perf_name != old_perf_name:
                    match = re.match(r"^(\d+)_", self.filename)
                    if match:
                        index = match.group(1)
                        new_filename = f"{index}_{new_perf_name}.ini"
                        ftp.rename(self.filename, new_filename)
                        self.harvester.log_message(f"✏️ Performance renamed: {self.filename} → {new_filename}")
                    else:
                        new_filename = f"{new_perf_name}.ini"
                        ftp.rename(self.filename, new_filename)
                        self.harvester.log_message(f"✏️ Performance renamed: {self.filename} → {new_filename}")
                self.parent.item_to_focus = new_filename
                ftp.close()
                ftp = None
                def finish():
                    self.refresh_callback()
                    self.destroy()
                self.after(100, finish)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", f"Save failed:\n{e}"))
                self.after(0, self.destroy)
            finally:
                if ftp:
                    try:
                        ftp.close()
                    except:
                        pass

        threading.Thread(target=upload_and_rename, daemon=True).start()