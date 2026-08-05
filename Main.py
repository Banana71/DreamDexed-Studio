# =============================================================================
# Main.py                                                                     =
#              --- ABSCHNITT 1: SETUP & KONFIGURATION ---                     =
# =============================================================================
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
from PIL import Image, ImageTk
import configparser
import json
import os
import queue
import threading
import shutil
import subprocess
from datetime import datetime
import ftplib
from pathlib import Path
import io
import re
import ctypes
from ctypes import wintypes
from harvester import PerfList_pdf_exp
from harvester import Perf2syx
from harvester import DX7_Roms
from harvester.perf2sheet import parse_voice_155, generate_datasheet, sanitize_filename
from harvester.constants import *
from harvester.widgets import ToolTip
from harvester.dialogs import ProfileManager
from harvester.ftp_utils import safe_ftp_operation
from harvester.update import UpdateDialog
from harvester.status import run_status_scan
import sys
from harvester.chord_scanner import ChordScanner
from harvester.midi_utils import list_midi_out_devices, send_bank_and_program, winmm
from harvester.minidexed_ini import parse_minidexed_ini
from harvester.midi_utils import list_midi_out_devices, send_bank_and_program, winmm, send_sysex
from harvester.about_dialog import show_about
from harvester.velocity_histogram_widget import VelocityHistogramWidget

if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_INI = os.path.join(BASE_DIR, 'config.ini')
CONFIG_JSON = os.path.join(BASE_DIR, 'config.json')
EXPORT_DIR = os.path.join(BASE_DIR, 'Export')

# =============================================================================
# --- HILFSFUNKTIONEN ---
# =============================================================================

def hex_to_text(hex_string):
    try:
        bytes_list = hex_string.strip().split()
        if len(bytes_list) < 11:
            return "UNKNOWN"
        name_bytes = bytes_list[-11:-1]
        chars = [chr(int(b, 16)) for b in name_bytes]
        return "".join(chars).rstrip('\x00')
    except:
        return "ERROR"

def text_to_hex(text):
    text = text.ljust(10)[:10]
    hex_bytes = [f"{ord(char):02X}" for char in text]
    return " ".join(hex_bytes)

def parse_ini_for_voices(lines):
    import re
    tg_map = {i: {'hex': '', 'channel': 1, 'line_idx': -1, 'link': 0} for i in range(1, 9)}
    regex_link = re.compile(r"^TGLink(\d+)=(\d+)")
    regex_ch = re.compile(r"^MIDIChannel(\d+)=(\d+)")
    regex_voice = re.compile(r"^VoiceData(\d+)=(.*)")

    for idx, line in enumerate(lines):
        line = line.strip()
        m_link = regex_link.match(line)
        if m_link:
            tg = int(m_link.group(1))
            if 1 <= tg <= 8:
                tg_map[tg]['link'] = int(m_link.group(2))
        m_ch = regex_ch.match(line)
        if m_ch:
            tg = int(m_ch.group(1))
            if 1 <= tg <= 8:
                tg_map[tg]['channel'] = int(m_ch.group(2))
        m_voice = regex_voice.match(line)
        if m_voice:
            tg = int(m_voice.group(1))
            if 1 <= tg <= 8:
                tg_map[tg]['hex'] = m_voice.group(2)
                tg_map[tg]['line_idx'] = idx
    return tg_map

def rebuild_ini_line(original_line, new_hex):
    parts = original_line.strip().split('=')
    if len(parts) != 2:
        return original_line
    value_part = parts[1].strip().split()
    if len(value_part) < 11:
        return original_line
    new_value = " ".join(value_part[:-11]) + " " + new_hex + " " + value_part[-1]
    return f"{parts[0]}={new_value}\n"

# =============================================================================
# --- HAUPTANWENDUNG (Harvester) ---
# =============================================================================
class Harvester(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DreamDexed Studio - The Seed Manager")
        self.scale = SCALE_FACTOR
        target_w = int(1224 * self.scale)
        target_h = int(860 * self.scale)
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        w = min(target_w, int(screen_w * 0.9))
        h = min(target_h, int(screen_h * 0.9))
        self.geometry(f"{w}x{h}")
        self.resizable(False, True)
        self.minsize(int(1024 * self.scale), int(750 * self.scale))
        self.config = configparser.ConfigParser()
        self.ftp_data = {}
        self.ftp_busy = False
        self._last_log_was_progress = False
        self.config_expanded = tk.BooleanVar(value=False)
        self.load_config()
        self.load_ftp_data()
        self.midi_device_index = self.config.getint('MIDI', 'device_index', fallback=0)
        self.midi_out_device_index = self.config.getint('MIDI', 'out_device_index', fallback=-1)
        self.midi_out_channel = self.config.getint('MIDI', 'out_channel', fallback=1)
        self.chord_scanner = None
        self.chord_timer = None
        self.velocity_queue = queue.Queue()      # <-- NEU
        # --- NEW: miniDexed configuration from Pi ---
        self.minidexed_config = None
        self.btn_midi_config = None
        self.midi_button_mapping = {}       # {function: keycode}
        self.midi_handle = None             # open MIDI output handle
        self.prog_buffer = ""               # program change buffer
        self.active_nav_pressed = set()     # currently pressed keycodes
        self._nav_logged_active = False
        self._chord_scanner_ready = False
        self._midi_nav_status_reported = False
        self._system_check_done = False
        # -------------------------------------------
        self.create_widgets()
        self.check_and_create_folders()
        self.after(100, self.init_explorer)

    def get_current_profile_name(self):
        name = self.combo_profile.get()
        return name if name else "unknown"

    def load_config(self):
        if not os.path.exists(CONFIG_INI):
            self.config['PATHS'] = {'base_path': BASE_DIR, 'github_dir': '', 'dexed_dir': ''}
            self.config['PDF'] = {'filename': 'Performance List.pdf', 'footer_text': 'https://soundplantage.com/ | DreamDexed Project'}
            self.config['DEFAULTS'] = {'watermark1': 'ONLY LOVE ', 'watermark2': 'BEATS HATE'}
            self.config['GUI'] = {'gui_scale_percent': '100'}
            self.config['MIDI'] = {'device_index': '0', 'out_device_index': '-1', 'out_channel': '1'}
        else:
            self.config.read(CONFIG_INI, encoding='utf-8')
            if 'dexed_dir' not in self.config['PATHS']:
                self.config['PATHS']['dexed_dir'] = ''
            if not self.config.has_section('DEFAULTS'):
                self.config['DEFAULTS'] = {'watermark1': 'ONLY LOVE ', 'watermark2': 'BEATS HATE'}
            if not self.config.has_section('GUI'):
                self.config['GUI'] = {'gui_scale_percent': '100'}
            if not self.config.has_section('MIDI'):
                self.config['MIDI'] = {'device_index': '0', 'out_device_index': '-1', 'out_channel': '1'}

    def save_config(self):
        try:
            wm1 = self.entry_wm1.get().strip()
            wm2 = self.entry_wm2.get().strip()
            if len(wm1) > 10:
                messagebox.showwarning("Length limit", f"Watermark 1 truncated to 10 characters: '{wm1[:10]}'")
                wm1 = wm1[:10]
                self.entry_wm1.delete(0, tk.END)
                self.entry_wm1.insert(0, wm1)
            if len(wm2) > 10:
                messagebox.showwarning("Length limit", f"Watermark 2 truncated to 10 characters: '{wm2[:10]}'")
                wm2 = wm2[:10]
                self.entry_wm2.delete(0, tk.END)
                self.entry_wm2.insert(0, wm2)

            if not self.config.has_section('PATHS'): self.config.add_section('PATHS')
            if not self.config.has_section('PDF'): self.config.add_section('PDF')
            if not self.config.has_section('DEFAULTS'): self.config.add_section('DEFAULTS')
            if not self.config.has_section('GUI'):   self.config.add_section('GUI')
            if not self.config.has_section('MIDI'):  self.config.add_section('MIDI')

            self.config.set('PATHS', 'base_path', self.entry_base_path.get())
            if hasattr(self, 'entry_dexed_path'):
                self.config.set('PATHS', 'dexed_dir', self.entry_dexed_path.get())
            if hasattr(self, 'entry_git_path'):
                self.config.set('PATHS', 'github_dir', self.entry_git_path.get())
            if hasattr(self, 'entry_pdf_name'):
                self.config.set('PDF', 'filename', self.entry_pdf_name.get())
            if hasattr(self, 'entry_pdf_footer'):
                self.config.set('PDF', 'footer_text', self.entry_pdf_footer.get())
            self.config.set('DEFAULTS', 'watermark1', wm1)
            self.config.set('DEFAULTS', 'watermark2', wm2)

            try:
                gui_val = int(self.entry_gui_scale.get().strip())
                gui_val = max(50, min(300, gui_val))
            except (ValueError, AttributeError):
                gui_val = 100
            self.config.set('GUI', 'gui_scale_percent', str(gui_val))

            self.config.set('MIDI', 'device_index', str(self.midi_device_index))
            self.config.set('MIDI', 'out_device_index', str(self.midi_out_device_index))
            self.config.set('MIDI', 'out_channel', str(self.midi_out_channel))

            with open(CONFIG_INI, 'w', encoding='utf-8') as f:
                self.config.write(f)
            self.log_message("Configuration saved in config.ini.")
        except Exception as e:
            self.log_message(f"Error saving config.ini: {str(e)}")

    def save_dx7_setting(self):
        if not self.config.has_section('DEFAULTS'):
            self.config.add_section('DEFAULTS')
        self.config.set('DEFAULTS', 'dx7_auto_convert', str(self.dx7_var.get()))
        try:
            with open(CONFIG_INI, 'w', encoding='utf-8') as f:
                self.config.write(f)
        except Exception as e:
            self.log_message(f"Error saving DX7 setting: {e}")

    def get_watermark1(self):
        return self.config.get('DEFAULTS', 'watermark1', fallback='ONLY LOVE ')[:10]
    def get_watermark2(self):
        return self.config.get('DEFAULTS', 'watermark2', fallback='BEATS HATE')[:10]

    def load_ftp_data(self):
        if os.path.exists(CONFIG_JSON):
            with open(CONFIG_JSON, 'r', encoding='utf-8') as f:
                self.ftp_data = json.load(f)
        else:
            self.ftp_data = {"profiles": {}, "last_used_profile": ""}

    def save_ftp_data(self):
        with open(CONFIG_JSON, 'w', encoding='utf-8') as f:
            json.dump(self.ftp_data, f, indent=4)

    def check_and_create_folders(self):
        base = self.entry_base_path.get()
        git = self.entry_git_path.get() if hasattr(self, 'entry_git_path') else ""
        dexed = self.entry_dexed_path.get() if hasattr(self, 'entry_dexed_path') else ""
        self.log_message("--- System Check started ---")
        all_ok = True
        if not os.path.exists(CONFIG_INI):
            self.log_message(f"Error: {CONFIG_INI} missing!")
            all_ok = False
        else:
            self.log_message(f"{CONFIG_INI} found.")

        folders_to_check = [
            (os.path.join(base, PERF_IMPORT), PERF_IMPORT),
            (os.path.join(base, EXPORT_DIR_NAME), EXPORT_DIR_NAME),
            (os.path.join(base, "VoiceSheets"), "VoiceSheets"),
            (os.path.join(base, "performance"), "performance"),
        ]

        for path, name in folders_to_check:
            if not os.path.exists(path):
                try:
                    os.makedirs(path)
                    self.log_message(f"Folder '{name}' created.")
                except Exception:
                    self.log_message(f"Could not create '{name}'.")
                    all_ok = False
            else:
                if name == EXPORT_DIR_NAME:
                    perf_path = os.path.join(path, 'performance')
                    if os.path.isdir(perf_path):
                        bank_count = 0
                        perf_count = 0
                        for bank in os.listdir(perf_path):
                            bank_dir = os.path.join(perf_path, bank)
                            if os.path.isdir(bank_dir) and not bank.startswith('.'):
                                bank_count += 1
                                for f in os.listdir(bank_dir):
                                    if f.lower().endswith('.ini'):
                                        perf_count += 1
                        if perf_count > 0:
                            self.log_message(f"Folder '{name}' ready. ** {perf_count} performances in {bank_count} banks **")
                        else:
                            self.log_message(f"Folder '{name}' ready.")
                    else:
                        self.log_message(f"Folder '{name}' ready.")
                elif name == "performance":
                    bank_count = 0
                    perf_count = 0
                    for bank in os.listdir(path):
                        bank_dir = os.path.join(path, bank)
                        if os.path.isdir(bank_dir) and not bank.startswith('.'):
                            bank_count += 1
                            for f in os.listdir(bank_dir):
                                if f.lower().endswith('.ini'):
                                    perf_count += 1
                    if perf_count > 0:
                        self.log_message(f"Folder '{name}' ready. ** {perf_count} performances in {bank_count} banks **")
                    else:
                        self.log_message(f"Folder '{name}' ready (empty).")
                elif name == "VoiceSheets":
                    try:
                        sheet_count = len([f for f in os.listdir(path) if f.lower().endswith('.txt')])
                        if sheet_count > 0:
                            self.log_message(f"Folder '{name}' ready. ** {sheet_count} VoiceSheets present **")
                        else:
                            self.log_message(f"Folder '{name}' ready.")
                    except Exception:
                        self.log_message(f"Folder '{name}' ready.")
                else:
                    self.log_message(f"Folder '{name}' ready.")

        if git and git.strip():
            if not os.path.exists(git):
                try:
                    os.makedirs(git)
                    self.log_message(f"GitHub repo folder created.")
                except Exception:
                    self.log_message(f"Could not create GitHub path.")
                    all_ok = False
            else:
                self.log_message("GitHub path ready.")
        if dexed and dexed.strip():
            if not os.path.exists(dexed):
                try:
                    os.makedirs(dexed)
                    self.log_message(f"Dexed folder created.")
                except Exception:
                    self.log_message(f"Could not create Dexed path.")
                    all_ok = False
            else:
                self.log_message("Dexed path ready.")
        if os.path.exists("DX7 Cartridges"):
            self.log_message("Folder 'DX7 Cartridges' ready.")
        else:
            self.log_message("Folder 'DX7 Cartridges' missing (DX7 import inactive).")

        current_profile = self.combo_profile.get()
        if current_profile:
            self.log_message(f"Device: {current_profile}")
        else:
            self.log_message("No device selected.")
        self.after(200, self._try_finish_system_check)

    def _try_finish_system_check(self):
        if self._system_check_done:
            return
        if self._chord_scanner_ready and self._midi_nav_status_reported:
            self.log_message("--- Core systems checked, System is Ready! ---")
            self._system_check_done = True

    def toggle_config(self):
        if self.config_expanded.get():
            self.config_content.pack_forget()
            self.config_expanded.set(False)
            self.btn_toggle_config.config(text="Expand   ▼")
        else:
            self.config_content.pack(fill="x", padx=10, pady=5)
            self.config_expanded.set(True)
            self.btn_toggle_config.config(text="Collapse ▲")
            self.refresh_midi_devices()

    def open_folder(self, path):
        if path and os.path.exists(path):
            subprocess.Popen(['explorer', path])
        else:
            self.log_message(f"Path does not exist: {path}")

    # -------------------------------------------------------------------------
    # GUI aufbauen
    # -------------------------------------------------------------------------
    def create_widgets(self):
        self.configure(bg=COLOR_BG)
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TLabelframe", background=COLOR_BG, foreground=COLOR_FG, bordercolor=COLOR_FG_DIM)
        style.configure("TLabelframe.Label", background=COLOR_BG, foreground=COLOR_FG, font=FONT_NORMAL)
        style.configure("TCombobox", fieldbackground=COLOR_BG, background=COLOR_BG, foreground=COLOR_FG, arrowcolor=COLOR_FG, font=FONT_NORMAL)
        style.map("TCombobox", fieldbackground=[("readonly", COLOR_BG)])
        style.configure("TCombobox.Listbox", font=FONT_NORMAL)
        style.configure("TButton", background=COLOR_BG_BUTTON, foreground=COLOR_FG, bordercolor=COLOR_FG_DIM, relief="raised")
        style.map("TButton", background=[("active", COLOR_BG_SELECT)])

        # --- Linker Haupt-Container (fix 626 * scale) ---
        main_frame = tk.Frame(self, bg=COLOR_BG, width=int(626 * self.scale))
        main_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        main_frame.pack_propagate(False)

        # --- Rechter Container für Explorer (fix 398 * scale) ---
        explorer_container = tk.Frame(self, bg=COLOR_BG, width=int(598 * self.scale))
        explorer_container.pack(side=tk.RIGHT, fill=tk.Y, expand=False)
        explorer_container.pack_propagate(False)
        self.explorer_container = explorer_container

        # ---- 1. Oberste Zeile: FTP ----
        frame_top = tk.Frame(main_frame, bg=COLOR_BG)
        frame_top.pack(fill="x", padx=10, pady=10)

        frame_ftp = tk.Frame(frame_top, bg=COLOR_BG)
        frame_ftp.pack(fill="x", pady=(0, 5))
        tk.Label(frame_ftp, text="Device:", font=FONT_BOLD, width=6, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        self.combo_profile = ttk.Combobox(frame_ftp, state="readonly", width=int(20 * self.scale))
        self.combo_profile.pack(side="left", padx=10)
        self.combo_profile.bind("<<ComboboxSelected>>", lambda e: self.update_last_profile())
        btn_style = {"bg": COLOR_BG_BUTTON, "fg": COLOR_FG, "activebackground": COLOR_BG_SELECT,
                     "activeforeground": COLOR_FG, "font": FONT_NORMAL, "relief": "raised"}
        tk.Button(frame_ftp, text="🔌 FTP Test", command=self.cmd_ftp_test, **btn_style).pack(side="left", padx=5)
        tk.Button(frame_ftp, text="⚙️ Edit Profiles", command=self.open_profile_manager, **btn_style).pack(side="left", padx=5)
        self.update_profile_dropdown()
        self.btn_reboot = tk.Button(frame_ftp, text="DreamDexed reboot", font=FONT_NORMAL, bg=COLOR_BG_BUTTON, fg=COLOR_FG_WARN, relief="raised", cursor="hand2", activebackground="#FFA6A6")
        self.btn_reboot.pack(side="left", padx=5)
        self._reboot_timer = None
        self.btn_reboot.bind("<ButtonPress-1>", self.on_reboot_press)
        self.btn_reboot.bind("<ButtonRelease-1>", self.on_reboot_release)
        self.btn_reboot.bind("<Leave>", self.on_reboot_release)

        # ---- 2. Ausklappbare Konfiguration ----
        self.config_frame = ttk.LabelFrame(main_frame, text="Paths, Configuration & Master Volume:")
        self.config_frame.pack(fill="x", padx=10, pady=(0, 10))

        toggle_frame = tk.Frame(self.config_frame, bg=COLOR_BG)
        toggle_frame.pack(fill="x")
        self.btn_toggle_config = tk.Button(toggle_frame, text="Expand   ▼", command=self.toggle_config,
                                           bg=COLOR_BG_BUTTON, fg=COLOR_FG, font=FONT_NORMAL, relief="raised")
        self.btn_toggle_config.pack(side="left", padx=5, pady=2)

        # --- Master Volume Slider ---
        self.master_volume = tk.IntVar(value=127)
        self.volume_slider = tk.Scale(
            toggle_frame,
            from_=0, to=127,
            orient=tk.HORIZONTAL,
            variable=self.master_volume,
            command=self._on_master_volume_change,
            showvalue=False,                     # <-- keine aufklappende Zahl
            bg=COLOR_BG_SLIDER,
            fg=COLOR_FG,
            troughcolor=COLOR_BG_BUTTON,
            highlightthickness=0,
            length=int(250 * SCALE_FACTOR),
            width=25,                            # <-- schmaler, passend zur Buttonhöhe
            sliderlength=int(30 * SCALE_FACTOR)
        )
        self.volume_slider.pack(side="left", fill="x", expand=True, padx=(20, 10), pady=2)

        self.lbl_volume_value = tk.Label(
            toggle_frame,
            text="127",
            font=FONT_NORMAL,
            fg=COLOR_FG,
            bg=COLOR_BG,
            width=4,
            anchor="w"
        )
        self.lbl_volume_value.pack(side="left", padx=(0, 10))

        # Logo rechts in der Toggle-Leiste
        logo_path = os.path.join(BASE_DIR, "harvester", "logo.png")
        if os.path.exists(logo_path):
            pil_image = Image.open(logo_path)
            target_height = int(40 * self.scale)
            aspect = pil_image.width / pil_image.height
            target_width = int(target_height * aspect)
            pil_image = pil_image.resize((target_width, target_height), Image.LANCZOS)
            self.logo_image_tk = ImageTk.PhotoImage(pil_image)
            self.lbl_logo = tk.Label(toggle_frame, image=self.logo_image_tk, bg=COLOR_BG)
            self.lbl_logo.pack(side="right", padx=10, pady=2)
            self.lbl_logo.bind("<Button-1>", lambda e: show_about(self, BASE_DIR))

        # Container für die Inhalte (wird ein-/ausgeklappt)
        self.config_content = tk.Frame(self.config_frame, bg=COLOR_BG)

        # Base Path
        row_base = tk.Frame(self.config_content, bg=COLOR_BG)
        row_base.pack(fill="x", pady=2)
        tk.Label(row_base, text="Base Path:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        btn_open_base = tk.Button(row_base, text="📂", command=lambda: self.open_folder(BASE_DIR),
                                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, font=FONT_NORMAL, relief="raised")
        btn_open_base.pack(side="right", padx=(5, 0))
        ToolTip(btn_open_base, "Open root folder in Explorer")

        self.entry_base_path = tk.Entry(row_base, bg=COLOR_BG_ENTRY, fg="white",
                                        insertbackground=COLOR_FG, font=FONT_NORMAL,
                                        readonlybackground=COLOR_BG_ENTRY)
        self.entry_base_path.insert(0, BASE_DIR)
        self.entry_base_path.config(state='readonly')
        self.entry_base_path.pack(side="left", padx=10, fill="x", expand=True)

        # Dexed Path
        row_dexed = tk.Frame(self.config_content, bg=COLOR_BG)
        row_dexed.pack(fill="x", pady=2)
        tk.Label(row_dexed, text="Dexed Path:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        btn_open_dexed = tk.Button(row_dexed, text="📂", command=lambda: self.open_folder(self.entry_dexed_path.get()),
                                   bg=COLOR_BG_BUTTON, fg=COLOR_FG, font=FONT_NORMAL, relief="raised")
        btn_open_dexed.pack(side="right", padx=(5, 0))
        ToolTip(btn_open_dexed, "Open Dexed folder if exists")

        self.entry_dexed_path = tk.Entry(row_dexed, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.entry_dexed_path.insert(0, self.config.get('PATHS', 'dexed_dir', fallback=''))
        self.entry_dexed_path.pack(side="left", padx=10, fill="x", expand=True)

        # GitHub Repo
        row_git = tk.Frame(self.config_content, bg=COLOR_BG)
        row_git.pack(fill="x", pady=2)
        tk.Label(row_git, text="GitHub Repo:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        btn_open_git = tk.Button(row_git, text="📂", command=lambda: self.open_folder(self.entry_git_path.get()),
                                 bg=COLOR_BG_BUTTON, fg=COLOR_FG, font=FONT_NORMAL, relief="raised")
        btn_open_git.pack(side="right", padx=(5, 0))
        ToolTip(btn_open_git, "Open GitHub repo folder if exists")

        self.entry_git_path = tk.Entry(row_git, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.entry_git_path.insert(0, self.config.get('PATHS', 'github_dir', fallback=''))
        self.entry_git_path.pack(side="left", padx=10, fill="x", expand=True)

        # PDF Name
        row_pdf1 = tk.Frame(self.config_content, bg=COLOR_BG)
        row_pdf1.pack(fill="x", pady=2)
        tk.Label(row_pdf1, text="PDF Name:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        self.entry_pdf_name = tk.Entry(row_pdf1, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.entry_pdf_name.insert(0, self.config.get('PDF', 'filename', fallback=''))
        self.entry_pdf_name.pack(side="left", padx=(10, 44), fill="x", expand=True)

        # PDF Footer
        row_pdf2 = tk.Frame(self.config_content, bg=COLOR_BG)
        row_pdf2.pack(fill="x", pady=2)
        tk.Label(row_pdf2, text="Footer:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        self.entry_pdf_footer = tk.Entry(row_pdf2, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.entry_pdf_footer.insert(0, self.config.get('PDF', 'footer_text', fallback=''))
        self.entry_pdf_footer.pack(side="left", padx=(10, 44), fill="x", expand=True)

        # Watermarks
        row_wm = tk.Frame(self.config_content, bg=COLOR_BG)
        row_wm.pack(fill="x", pady=2)

        tk.Label(row_wm, text="Watermark 1:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        self.entry_wm1 = tk.Entry(row_wm, width=21, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.entry_wm1.insert(0, self.get_watermark1())
        self.entry_wm1.pack(side="left", padx=10)

        tk.Label(row_wm, text="Watermark 2:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left", padx=(20,0))
        self.entry_wm2 = tk.Entry(row_wm, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.entry_wm2.insert(0, self.get_watermark2())
        self.entry_wm2.pack(side="left", padx=10, fill="x", expand=True)

        btn_open_voicesheets = tk.Button(row_wm, text="📂",
                                         command=lambda: self.open_folder(os.path.join(BASE_DIR, "VoiceSheets")),
                                         bg=COLOR_BG_BUTTON, fg=COLOR_FG, font=FONT_NORMAL, relief="raised")
        btn_open_voicesheets.pack(side="right", padx=(5,0))
        ToolTip(btn_open_voicesheets, "Open VoiceSheets folder")

        # --- GUI Skalierung ---
        row_gui_scale = tk.Frame(self.config_content, bg=COLOR_BG)
        row_gui_scale.pack(fill="x", pady=2)
        tk.Label(row_gui_scale, text="GUI Scale:", font=FONT_BOLD, width=11, anchor="w",
                 bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        self.entry_gui_scale = tk.Entry(row_gui_scale, width=8, bg=COLOR_BG_ENTRY, fg=COLOR_FG,
                                        insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.entry_gui_scale.insert(0, self.config.get('GUI', 'gui_scale_percent', fallback='100'))
        self.entry_gui_scale.pack(side="left", padx=10)
        tk.Label(row_gui_scale, text="%", bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).pack(side="left")
        tk.Label(row_gui_scale, text="(75–300%, 100% = Default, restart required)", bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_NORMAL).pack(side="left", padx=10)

        # --- MIDI Zeile (In + Out + Kanal) ---
        row_midi = tk.Frame(self.config_content, bg=COLOR_BG)
        row_midi.pack(fill="x", pady=2)
        tk.Label(row_midi, text="MIDI In:", font=FONT_BOLD, width=11, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left")
        self.combo_midi = ttk.Combobox(row_midi, state="readonly", width=int(20 * self.scale))
        self.combo_midi.pack(side="left", padx=(5,0))
        self.combo_midi.bind("<<ComboboxSelected>>", self.on_midi_device_changed)
        ToolTip(self.combo_midi, "Select MIDI input device for chord detection.\n'Kein MIDI' disables the scanner.")

        tk.Label(row_midi, text="MIDI Out:", font=FONT_BOLD, width=9, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left", padx=(15,0))
        self.combo_midi_out = ttk.Combobox(row_midi, state="readonly", width=int(20 * self.scale))
        self.combo_midi_out.pack(side="left", padx=(5,0))
        self.combo_midi_out.bind("<<ComboboxSelected>>", self.on_midi_out_changed)
        ToolTip(self.combo_midi_out, "Select MIDI output device for program change.\n'Kein MIDI' disables sending.")

        tk.Label(row_midi, text="Chn:", font=FONT_BOLD, anchor="w", bg=COLOR_BG, fg=COLOR_FG).pack(side="left", padx=(15,0))
        self.lbl_perf_channel = tk.Label(row_midi, text="1", font=FONT_NORMAL,
                                         fg=COLOR_FG, bg=COLOR_BG, width=3, anchor="w")
        self.lbl_perf_channel.pack(side="left", padx=(5,0))
        ToolTip(self.lbl_perf_channel, "PerformanceSelectChannel imported from minidexed.ini")

        # --- NEW: MIDI Button Navigation status row ---
        row_midi_nav = tk.Frame(self.config_content, bg=COLOR_BG)
        row_midi_nav.pack(fill="x", pady=2)

        tk.Label(row_midi_nav, text="", width=13, bg=COLOR_BG).pack(side="left")

        self.lbl_midi_nav_status = tk.Label(
            row_midi_nav,
            text="MIDI Button Navigation: OFF",
            font=FONT_NORMAL,
            fg=COLOR_FG_DIM,
            bg=COLOR_BG,
            anchor="w"
        )
        self.lbl_midi_nav_status.pack(side="left", padx=(0, 10))

        self.btn_midi_config = tk.Button(
            row_midi_nav,
            text="MIDI Button Config",
            bg=COLOR_BG_BUTTON,
            fg=COLOR_FG,
            activebackground=COLOR_BG_SELECT,
            activeforeground=COLOR_FG,
            font=FONT_NORMAL,
            relief="raised",
            state="disabled",
            command=self.open_midi_button_config
        )
        self.btn_midi_config.pack(side="left")
        ToolTip(self.lbl_midi_nav_status, "Status of miniDexed button navigation (read from minidexed.ini).")
        ToolTip(self.btn_midi_config, "Assign PC keys to miniDexed button functions.")
        # --- END NEW ---

        # Save button
        row_save = tk.Frame(self.config_content, bg=COLOR_BG)
        row_save.pack(fill="x", pady=5)
        self.btn_save_config = tk.Button(row_save, text="💾 Save Config", command=self.save_config,
                                         bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                                         activeforeground=COLOR_FG, font=FONT_NORMAL, relief="raised")
        self.btn_save_config.pack(side="left", padx=5)
        ToolTip(self.btn_save_config, "Save Dexed path, GitHub path, PDF options and watermarks permanently in config.ini")

        # ---- 3. Workspace (Workflow) ----
        workflow_frame = ttk.LabelFrame(main_frame, text="Workspace")
        workflow_frame.pack(fill="x", padx=10, pady=10)

        # Variablen vor den Widgets initialisieren
        self.dx7_var = tk.BooleanVar()
        self.dx7_var.set(self.config.getboolean('DEFAULTS', 'dx7_auto_convert', fallback=False))

        # DX7-Checkbox und Export-Ziele – exakt über den Buttons
        chk_frame = tk.Frame(workflow_frame, bg=COLOR_BG)
        chk_frame.pack(fill="x", padx=10, pady=(5, 0))

        # 1) Platzhalter für Button 1 (gleiche Breite wie der Button)
        ph_btn1 = tk.Label(chk_frame, text="", width=24, font=FONT_BOLD, bg=COLOR_BG)
        ph_btn1.pack(side="left", padx=5)

        # 2) Pfeil-Platzhalter (gleiche Breite wie das Label)
        ph_arrow1 = tk.Label(chk_frame, text="", font=FONT_TITLE, bg=COLOR_BG, width=2)
        ph_arrow1.pack(side="left", padx=2)

        # 3) DX7-Checkbox (über Button 2)
        chk = tk.Checkbutton(chk_frame, text="Add DX7 ROMs", variable=self.dx7_var,
                     bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_BG, activebackground=COLOR_BG,
                     font=FONT_NORMAL, command=self.save_dx7_setting)
        chk.pack(side="left", padx=5)
        ToolTip(chk, "If checked, all .syx files …")

        # 4) Pfeil-Platzhalter
        ph_arrow2 = tk.Label(chk_frame, text="", font=FONT_TITLE, bg=COLOR_BG, width=2)
        ph_arrow2.pack(side="left", padx=2)

        # 5) Export-Ziele (über Button 3)
        export_check_frame = tk.Frame(chk_frame, bg=COLOR_BG)
        export_check_frame.pack(side="left", padx=5)
        self.export_rpi_var = tk.BooleanVar(value=True)
        self.export_github_var = tk.BooleanVar(value=True)
        cb_rpi = tk.Checkbutton(export_check_frame, text="RPi", variable=self.export_rpi_var,
                                bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_BG,
                                activebackground=COLOR_BG, font=FONT_NORMAL)
        cb_rpi.pack(side="left", padx=2)
        cb_github = tk.Checkbutton(export_check_frame, text="GitHub & Dexed", variable=self.export_github_var,
                                   bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_BG,
                                   activebackground=COLOR_BG, font=FONT_NORMAL)
        cb_github.pack(side="left", padx=2)

        # Main workflow (1→2→3)
        btn_container = tk.Frame(workflow_frame, bg=COLOR_BG)
        btn_container.pack(pady=(5, 5))

        btn_workflow_base = {
            "bg": COLOR_BG_BUTTON,
            "fg": COLOR_FG,
            "activebackground": COLOR_BG_SELECT,
            "activeforeground": COLOR_FG,
            "font": FONT_BOLD,
            "width": 18,
            "height": 1,
            "cursor": "hand2",
            "relief": "raised"
        }

        self.btn_import = tk.Button(btn_container, text="1. Import from RPi", command=self.cmd_rpi_import, **btn_workflow_base)
        self.btn_import.pack(side="left", padx=5)
        ToolTip(self.btn_import, "Fetches current data from RPi to local working folder.")

        tk.Label(btn_container, text="➡", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG).pack(side="left", padx=2)

        self.btn_konvertieren = tk.Button(btn_container, text="2. Convert", command=self.cmd_konvertieren, **btn_workflow_base)
        self.btn_konvertieren.pack(side="left", padx=5)
        ToolTip(self.btn_konvertieren, "Extracts Sysex, adjusts performances and creates PDF in export folder.\nIf 'Add DX7 ROMs' is checked, DX7 patches are also integrated.")

        tk.Label(btn_container, text="➡", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG).pack(side="left", padx=2)

        # Export-Button (umbenannt)
        self.btn_verteilen = tk.Button(btn_container, text="3. Export", command=self.cmd_verteilen, **btn_workflow_base)
        self.btn_verteilen.pack(side="left", padx=5)
        ToolTip(self.btn_verteilen, "Transfers finished data to selected targets (RPi, GitHub & Dexed).")

        separator = ttk.Separator(workflow_frame, orient='horizontal')
        separator.pack(fill='x', padx=20, pady=10)

        # Utility buttons (lower row)
        tools_container = tk.Frame(workflow_frame, bg=COLOR_BG)
        tools_container.pack(pady=(5, 15))

        btn_tools_base = {
            "bg": COLOR_BG_BUTTON,
            "fg": COLOR_FG,
            "activebackground": COLOR_BG_SELECT,
            "activeforeground": COLOR_FG,
            "font": FONT_SMALL,
            "relief": "raised",
            "cursor": "hand2",
            "width": 18
        }

        # Soundplantage Update Button
        btn_update = tk.Button(tools_container, text="Update", command=self.cmd_update, **btn_tools_base)
        btn_update.pack(side="left", padx=5, ipady=2, ipadx=8)
        ToolTip(btn_update, "Download latest performances from Soundplantage GitHub and write to RPi")

        btn_status = tk.Button(tools_container, text="Status", command=self.cmd_status, **btn_tools_base)
        btn_status.pack(side="left", padx=5, ipady=2, ipadx=8)
        ToolTip(btn_status, "Local INIT scan & remote bank overview.")

        # ---- 4. Log (mit integrierter Akkord‑Anzeige) ----
        log_frame = tk.Frame(main_frame, bg=COLOR_BG)
        log_frame.pack(fill="both", expand=True, padx=10, pady=0)

        # Header mit "Log" und Akkord-Anzeige in einer Zeile
        header_frame = tk.Frame(log_frame, bg=COLOR_BG)
        header_frame.pack(fill="x")

        lbl_log = tk.Label(header_frame, text="Log", font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_FG, anchor="w")
        lbl_log.pack(side="left", anchor="s")

        # --- Velocity Histogramm (links vom Chord Scanner) ---
        self.velocity_histogram = VelocityHistogramWidget(
            header_frame,
            velocity_queue=self.velocity_queue,
            bg=COLOR_BG_CHORD 
        )
        self.velocity_histogram.pack(side="left", padx=(16, 0))
        # --------------------------------------------------------

        # Akkord-Anzeige 
        self.chord_frame = tk.Frame(header_frame, bg=COLOR_BG_CHORD,
                               highlightthickness=1) 
        self.chord_frame.pack(side="left", padx=(20, 16)) 

        chord_font = (CHORD_FONT_FAMILY, int(CHORD_FONT_SIZE * self.scale), "bold")
        self.chord_label = tk.Label(
            self.chord_frame,
            text="",
            font=chord_font,
            fg=COLOR_FG_CHORD,
            bg=COLOR_BG_CHORD,
            anchor="center",
            width=16,
            height=1
        )
        self.chord_label.pack(padx=4, pady=0)

        self.log_area = scrolledtext.ScrolledText(log_frame, state='disabled',
                                                  bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL)
        self.log_area.pack(fill="both", expand=True, padx=5, pady=5)

        self.after(100, self._sync_histogram_size)
        self.after(100, self.start_chord_scanner)

    # -------------------------------------------------------------------------
    # Explorer einbinden
    # -------------------------------------------------------------------------
    def init_explorer(self):
        """Erzeugt den Performance-Manager-Frame und startet Verbindungsversuch."""
        from harvester.performance_manager import PerformanceManagerFrame
        self.explorer_frame = PerformanceManagerFrame(
            master=self.explorer_container,
            harvester=self
        )
        self.explorer_frame.pack(fill=tk.BOTH, expand=True)
        self.explorer_frame.connect_and_refresh()

    # -------------------------------------------------------------------------
    # Profile & FTP
    # -------------------------------------------------------------------------
    def update_profile_dropdown(self):
        profiles = list(self.ftp_data.get("profiles", {}).keys())
        self.combo_profile['values'] = profiles
        last_used = self.ftp_data.get("last_used_profile", "")
        if last_used in profiles:
            self.combo_profile.set(last_used)
        elif profiles:
            self.combo_profile.set(profiles[0])

    def update_last_profile(self):
        self.ftp_data["last_used_profile"] = self.combo_profile.get()
        self.save_ftp_data()
        self.log_message(f"Device selected: {self.combo_profile.get()}")
        if hasattr(self, 'explorer_frame') and self.explorer_frame:
            self.explorer_frame.connect_and_refresh()
        # ---------------------------------------------------------

    def get_active_ftp_creds(self):
        prof_name = self.combo_profile.get()
        if not prof_name or prof_name not in self.ftp_data.get("profiles", {}):
            self.log_message("Please select a valid FTP profile first.")
            return None
        creds = self.ftp_data["profiles"][prof_name]
        if not creds.get("ip", "").strip():
            self.log_message("Selected profile has no IP address.")
            return None
        return creds

    def open_profile_manager(self):
        from harvester.dialogs import ProfileManager
        ProfileManager(
            self,
            self.ftp_data,
            self.save_ftp_data,
            self.update_profile_dropdown,
            DEFAULT_FTP_USER,
            DEFAULT_FTP_PASS
        )

    def log_message(self, message):
        self.log_area.config(state='normal')
        self._last_log_was_progress = False
        self.log_area.insert(tk.END, message + "\n")
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')

    def log_progress(self, message):
        self.log_area.config(state='normal')
        if getattr(self, '_last_log_was_progress', False):
            self.log_area.delete("end-2l linestart", "end-2l lineend")
            self.log_area.insert("end-2l linestart", message)
        else:
            self.log_area.insert(tk.END, message + "\n")
            self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        self._last_log_was_progress = True

    def clear_progress(self):
        if getattr(self, '_last_log_was_progress', False):
            self.log_area.config(state='normal')
            self.log_area.delete("end-2l linestart", "end-1l")
            self.log_area.config(state='disabled')
            self._last_log_was_progress = False

    # -------------------------------------------------------------------------
    # Workflow-Methoden
    # -------------------------------------------------------------------------
    def cmd_konvertieren(self):
        self.log_message("\n--- STARTING STEP 2: CONVERT ---")
        base = self.entry_base_path.get()
        indir = Path(base) / PERF_IMPORT
        export_dir = Path(base) / EXPORT_DIR_NAME
        backup_base = Path(base) / "_backups"
        backup_base.mkdir(parents=True, exist_ok=True)
        backup_folder_name = datetime.now().strftime("Export_%Y%m%d_%H%M%S")
        backup_dir = backup_base / backup_folder_name
        if export_dir.exists():
            try:
                shutil.move(str(export_dir), str(backup_dir))
                self.log_message(f"Backup: Old export folder moved to /_backups/{backup_folder_name}")
            except Exception as e:
                self.log_message(f"[WARNING] Could not move export folder. Error: {e}")
                return
        out_dexed_dir = export_dir / "Soundplantage"
        out_syx_dir = export_dir / "sysex" / "voice"
        folder_out_perf = export_dir / "performance"
        for d in [out_dexed_dir, out_syx_dir, folder_out_perf]:
            d.mkdir(parents=True, exist_ok=True)

        def task():
            try:
                self.log_message("Running conversion...")
                Perf2syx.run_conversion(indir=indir, out_dexed_dir=out_dexed_dir, out_syx_dir=out_syx_dir,
                                         folder_out_perf=folder_out_perf, start_bank=1, log_callback=self.log_message)
                if self.dx7_var.get():
                    self.log_message("DX7 integration enabled – adding ROMs and additional Sysex files.")
                    voice_dir = out_syx_dir
                    max_idx = -1
                    if voice_dir.exists():
                        for f in voice_dir.iterdir():
                            if f.suffix.lower() == '.syx':
                                m = re.match(r'^(\d+)_', f.name)
                                if m:
                                    idx = int(m.group(1))
                                    if idx > max_idx:
                                        max_idx = idx
                    start_idx = max_idx + 1 if max_idx >= 0 else 1
                    DX7_Roms.integrate_dx7_data(self.log_message, start_index=start_idx, force_clean=True)
                self.log_message("Creating PDF documentation...")
                pdf_filepath = export_dir / self.entry_pdf_name.get()
                footer = self.entry_pdf_footer.get()
                erfolg, nachricht = PerfList_pdf_exp.generate_pdf(str(folder_out_perf), str(pdf_filepath), footer)
                if erfolg:
                    self.log_message(f"PDF created: {nachricht}")
                else:
                    self.log_message(f"PDF creation error: {nachricht}")
                self.log_message("Conversion finished successfully. Ready for Export!")
            except Exception as e:
                self.log_message(f"[ERROR] During conversion: {str(e)}")
        threading.Thread(target=task, daemon=True).start()

    def cmd_verteilen(self):
        if self.ftp_busy:
            self.log_message("Please wait, FTP is busy...")
            return
        creds = self.get_active_ftp_creds()
        if not creds and self.export_rpi_var.get():
            self.log_message("RPi export is enabled but no valid FTP profile selected.")
            return
        self.ftp_busy = True
        def task():
            try:
                base = self.entry_base_path.get()
                dexed_pfad = self.entry_dexed_path.get()
                github_pfad = self.entry_git_path.get()
                export_dir = os.path.join(base, EXPORT_DIR_NAME)
                export_perf = os.path.join(export_dir, 'performance')
                export_syx = os.path.join(export_dir, "sysex")
                export_dexed = os.path.join(export_dir, "Soundplantage")
                pdf_src = os.path.join(export_dir, self.entry_pdf_name.get())
                self.log_message("\n--- STARTING STEP 3: EXPORT ---")

                # ----- RPi Upload -----
                if self.export_rpi_var.get():
                    self.log_message(f"Transferring data to {self.get_current_profile_name()} ({creds['ip']})...")

                    def ftp_upload(ftp):
                        ftp.cwd("/")
                        try: ftp.cwd("SD")
                        except: pass
                        root_dir = ftp.pwd()

                        # Sysex-Dateien
                        try:
                            ftp.cwd("sysex")
                            try: ftp.cwd("voice")
                            except: ftp.mkd("voice"); ftp.cwd("voice")
                        except:
                            ftp.mkd("sysex")
                            ftp.cwd("sysex")
                            ftp.mkd("voice")
                            ftp.cwd("voice")
                        local_syx_voice = os.path.join(export_syx, "voice")
                        if os.path.exists(local_syx_voice):
                            local_files = [f for f in os.listdir(local_syx_voice) if f.endswith(".syx")]
                            remote_files = []
                            ftp.retrlines('NLST', remote_files.append)
                            for file_name in local_files:
                                if "_" in file_name:
                                    prefix = file_name.split("_")[0] + "_"
                                    for remote_file in remote_files:
                                        if remote_file.startswith(prefix) and remote_file.endswith(".syx"):
                                            self.log_progress(f" Deleting old slot on Pi: {remote_file}")
                                            try: ftp.delete(remote_file)
                                            except: pass
                                self.log_progress(f" Writing Syx: {file_name}")
                                with open(os.path.join(local_syx_voice, file_name), 'rb') as f:
                                    ftp.storbinary(f"STOR {file_name}", f)
                        self.clear_progress()
                        self.log_message("Syx files transferred to DreamDexed.")

                        # Performances
                        ftp.cwd(root_dir)
                        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                        backup_name = f"performance_bu_{timestamp}"
                        try:
                            ftp.rename("performance", backup_name)
                            self.log_message(f"DreamDexed backup created: 'performance' -> '{backup_name}'.")
                        except Exception:
                            self.log_message("No existing 'performance' folder found on DreamDexed.")
                        try: ftp.mkd("performance")
                        except: pass
                        ftp.cwd("performance")
                        if os.path.exists(export_perf):
                            for folder_name in os.listdir(export_perf):
                                folder_path = os.path.join(export_perf, folder_name)
                                if os.path.isdir(folder_path):
                                    try: ftp.cwd(folder_name)
                                    except: ftp.mkd(folder_name); ftp.cwd(folder_name)
                                    for file_name in os.listdir(folder_path):
                                        if file_name.endswith(".ini"):
                                            self.log_progress(f" Writing INI: {folder_name}/{file_name}")
                                            with open(os.path.join(folder_path, file_name), 'rb') as f:
                                                ftp.storbinary(f"STOR {file_name}", f)
                                    ftp.cwd("..")
                        self.clear_progress()
                        self.log_message("Performances transferred to DreamDexed.")

                        # PDF auf RPi
                        if os.path.exists(pdf_src):
                            ftp.cwd(root_dir)
                            self.log_progress(f" Uploading PDF: {self.entry_pdf_name.get()}")
                            with open(pdf_src, 'rb') as f:
                                ftp.storbinary(f"STOR {self.entry_pdf_name.get()}", f)
                            self.clear_progress()
                            self.log_message("PDF transferred to DreamDexed.")
                        else:
                            self.log_message("PDF not found locally – skipping upload.")
                        return None

                    safe_ftp_operation(creds, ftp_upload, self.log_message)
                    self.log_message("Restart DreamDexed for new Sysex files to take effect.")
                else:
                    self.log_message("RPi export skipped (checkbox unchecked).")

                # ----- GitHub & Dexed -----
                if self.export_github_var.get():
                    if dexed_pfad and dexed_pfad.strip() and os.path.exists(dexed_pfad):
                        self.log_message(f"Cleaning up Dexed folder: {dexed_pfad}")
                        geloescht = 0
                        for f in os.listdir(dexed_pfad):
                            if f.endswith(".syx"):
                                os.remove(os.path.join(dexed_pfad, f))
                                geloescht += 1
                        if geloescht > 0:
                            self.log_message(f"{geloescht} old Syx files removed locally.")
                        self.log_message("Copying new Syx files to Dexed folder...")
                        shutil.copytree(export_dexed, dexed_pfad, dirs_exist_ok=True)
                        self.log_message("Dexed sync completed.")
                    if github_pfad and github_pfad.strip() and os.path.exists(github_pfad):
                        github_perf_target = os.path.join(github_pfad, 'performance')
                        if os.path.exists(github_perf_target):
                            self.log_message("Cleaning up GitHub 'performance' folder...")
                            shutil.rmtree(github_perf_target)
                        self.log_message(f"Updating GitHub repo: {github_pfad}")
                        shutil.copytree(export_perf, github_perf_target, dirs_exist_ok=True)
                        if os.path.exists(pdf_src):
                            shutil.copy2(pdf_src, os.path.join(github_pfad, self.entry_pdf_name.get()))
                        self.log_message("GitHub sync completed.")
                else:
                    self.log_message("GitHub & Dexed export skipped (checkbox unchecked).")

                self.log_message("Export completely finished!")

            except Exception as e:
                self.log_message(f"[ERROR] During distribution: {str(e)}")
            finally:
                self.ftp_busy = False
        threading.Thread(target=task, daemon=True).start()

    def cmd_ftp_test(self):
        if self.ftp_busy:
            self.log_message("Please wait, FTP is busy...")
            return
        creds = self.get_active_ftp_creds()
        if not creds: return
        self.ftp_busy = True
        def task():
            try:
                def ftp_op(ftp):
                    self.log_message(f"\n--- FTP Test:  {self.get_current_profile_name()} ({creds['ip']}) ---")
                    self.log_message("Connected!")
                    ftp.cwd("/")
                    try: ftp.cwd("SD")
                    except: pass
                    self.log_message(f"Current directory on {self.get_current_profile_name()}: {ftp.pwd()}")
                    self.log_message("Reading first 7 lines from minidexed.ini...")
                    lines = []
                    try:
                        ftp.retrlines('RETR minidexed.ini', lines.append)
                        self.log_message("--- minidexed.ini ---")
                        for line in lines[:8]:
                            self.log_message(line)
                        self.log_message("------------------------------")
                    except Exception as e:
                        self.log_message(f"minidexed.ini not found: {e}")
                    self.log_message("Test finished.")
                    return None
                safe_ftp_operation(creds, ftp_op, self.log_message)
            except Exception as e:
                self.log_message(f"FTP error: {e}")
            finally:
                self.ftp_busy = False
        threading.Thread(target=task, daemon=True).start()

    def cmd_rpi_import(self):
        if self.ftp_busy:
            self.log_message("Please wait, FTP is busy...")
            return
        creds = self.get_active_ftp_creds()
        if not creds: return
        self.ftp_busy = True
        def fetch_folders_task():
            try:
                def ftp_op(ftp):
                    self.log_message(f"\n--- RPi Import: Loading folder structure {self.get_current_profile_name()} ({creds['ip']}) ---")
                    ftp.cwd("/")
                    try: ftp.cwd("SD")
                    except: pass
                    try: ftp.cwd("performance")
                    except:
                        self.log_message("Folder 'performance' not found on RPi.")
                        return []
                    folders = []
                    def parse_line(line):
                        line = line.strip()
                        if "<DIR>" in line:
                            folders.append(line.split("<DIR>", 1)[1].strip())
                        elif line.startswith('d'):
                            parts = line.split(maxsplit=8)
                            if len(parts) == 9:
                                folders.append(parts[8].strip())
                    ftp.retrlines('LIST', parse_line)
                    return folders
                folders = safe_ftp_operation(creds, ftp_op, self.log_message)
                self.ftp_busy = False
                if not folders:
                    self.log_message("No subfolders found in /performance.")
                    return
                folders.sort()
                from harvester.dialogs import ImportDialog
                self.after(0, lambda: ImportDialog(self, folders, 
                            lambda sel, del_all: self.start_import_download(sel, del_all)))
            except Exception as e:
                self.log_message(f"FTP error during connection: {e}")
                self.ftp_busy = False
        threading.Thread(target=fetch_folders_task, daemon=True).start()

    def start_import_download(self, selected_folders, delete_all=False):
        if not selected_folders:
            self.log_message("Import cancelled or no folders selected.")
            return
        creds = self.get_active_ftp_creds()
        self.ftp_busy = True
        def download_task():
            try:
                base = self.entry_base_path.get()
                local_perf = os.path.join(base, PERF_IMPORT)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = os.path.join(base, '_backups', f"performance_pre_import_{timestamp}")
                if os.path.exists(local_perf):
                    shutil.copytree(local_perf, backup_path)
                    self.log_message(f"Local backup created: {backup_path}")

                if delete_all and os.path.exists(local_perf):
                    shutil.rmtree(local_perf)
                    os.path.normpath(local_perf)
                    self.log_message(f"{os.path.normpath(local_perf)} cleared")

                for folder in selected_folders:
                    target_dir = os.path.join(local_perf, folder)
                    if os.path.exists(target_dir):
                        shutil.rmtree(target_dir)
                if not os.path.exists(local_perf):
                    os.makedirs(local_perf)
                def ftp_op(ftp):
                    ftp.cwd("/")
                    try: ftp.cwd("SD")
                    except: pass
                    ftp.cwd("performance")
                    for folder in selected_folders:
                        local_folder = os.path.join(local_perf, folder)
                        os.makedirs(local_folder, exist_ok=True)
                        try: ftp.cwd(folder)
                        except:
                            self.log_message(f"Folder '{folder}' could not be opened on RPi.")
                            continue
                        files = []
                        def parse_files(line):
                            if ".ini" not in line.lower() or "<DIR>" in line:
                                return
                            line = line.strip()
                            if line.startswith('-'):
                                parts = line.split(maxsplit=8)
                                if len(parts) == 9:
                                    files.append(parts[8].strip())
                            else:
                                parts = line.split(maxsplit=3)
                                if len(parts) == 4:
                                    files.append(parts[3].strip())
                        ftp.retrlines('LIST', parse_files)
                        for file in files:
                            self.log_progress(f" Downloading: {folder}/{file}")
                            local_file = os.path.join(local_folder, file)
                            with open(local_file, 'wb') as f:
                                ftp.retrbinary(f"RETR {file}", f.write)
                        ftp.cwd("..")
                        self.clear_progress()
                        self.log_message(f"{folder} imported.")
                safe_ftp_operation(creds, ftp_op, self.log_message)
                self.log_message(f"All selected folders imported from {self.get_current_profile_name()}.")
            except Exception as e:
                self.log_message(f"FTP error during download: {e}")
            finally:
                self.ftp_busy = False
        threading.Thread(target=download_task, daemon=True).start()

    def cmd_reboot_pi(self):
        if self.ftp_busy:
            self.log_message("Please wait, FTP is currently busy...")
            return
        creds = self.get_active_ftp_creds()
        if not creds: return
        def reboot_task():
            self.ftp_busy = True
            self.log_message(f"\n--- Sending reboot signal to {self.get_current_profile_name()} ({creds['ip']}) ---")
            ftp = None
            try:
                ftp = ftplib.FTP(creds['ip'], timeout=5)
                ftp.login(creds['user'], creds['password'])
                try:
                    ftp.quit()
                    self.log_message("FTP quit sent. Device rebooting.")
                except Exception:
                    self.log_message("Connection closed. DreamDexed is restarting.")
            except Exception as e:
                self.log_message(f"Error sending reboot signal: {e}")
            finally:
                if ftp:
                    try:
                        ftp.close()
                    except:
                        pass
                self.ftp_busy = False
        threading.Thread(target=reboot_task, daemon=True).start()

    def on_reboot_press(self, event):
        if self.ftp_busy:
            self.log_message("Please wait, FTP is currently busy...")
            return
        creds = self.get_active_ftp_creds()
        if not creds:
            self.log_message("Aborted: FTP server not connected / No IP configured.")
            return
        self.btn_reboot.config(text="  * * Hold for 2s * *  ", bg=COLOR_BG_SELECT)
        self._reboot_timer = self.btn_reboot.after(2000, self.execute_reboot)

    def on_reboot_release(self, event):
        if self._reboot_timer:
            self.btn_reboot.after_cancel(self._reboot_timer)
            self._reboot_timer = None
        self.btn_reboot.config(text="DreamDexed reboot", bg=COLOR_BG_BUTTON)

    def execute_reboot(self):
        self._reboot_timer = None
        self.btn_reboot.config(text="* * Reboot sent! * *", bg=COLOR_BG_SELECT)
        self.cmd_reboot_pi()
        self.btn_reboot.after(1000, lambda: self.btn_reboot.config(text="DreamDexed reboot", bg=COLOR_BG_BUTTON))

    # cmd_performance_manager ENTFERNT

    def cmd_update(self):
        if self.ftp_busy:
            self.log_message("Please wait, FTP is busy...")
            return
        creds = self.get_active_ftp_creds()
        if not creds:
            return
        self.log_message("--- Soundplantage Update opened ---")
        UpdateDialog(self, creds, self)

    def cmd_status(self):
        """Startet den Status-Scan im Hintergrund."""
        self.log_message("\n - - - STATUS SCAN - - -")
        run_status_scan(self)

    # --- MIDI-Geräteauswahl und Chord Scanner ---
    def refresh_midi_devices(self):
        """Aktualisiert MIDI-In und MIDI-Out Comboboxen."""
        # MIDI In
        devices = ChordScanner.list_devices()
        values_in = ["Kein MIDI"] + devices
        self.combo_midi['values'] = values_in
        idx = self.midi_device_index
        if idx < 0 or idx >= len(devices):
            self.combo_midi.set("Kein MIDI")
            if idx != -1:
                self.log_message(f"MIDI-In device index {idx} not available – set to 'Kein MIDI'.")
                self.midi_device_index = -1
                self.save_config()
        else:
            self.combo_midi.current(idx + 1)

        # MIDI Out
        out_devices = list_midi_out_devices()
        values_out = ["Kein MIDI"] + out_devices
        self.combo_midi_out['values'] = values_out
        out_idx = self.midi_out_device_index
        if out_idx < 0 or out_idx >= len(out_devices):
            self.combo_midi_out.set("Kein MIDI")
            if out_idx != -1:
                self.log_message(f"MIDI-Out device index {out_idx} not available – set to 'Kein MIDI'.")
                self.midi_out_device_index = -1
                self.save_config()
        else:
            self.combo_midi_out.current(out_idx + 1)

    def on_midi_device_changed(self, event=None):
        selection = self.combo_midi.get()
        if selection == "Kein MIDI":
            new_index = -1
        else:
            devices = ChordScanner.list_devices()
            try:
                new_index = devices.index(selection)
            except ValueError:
                return
        if new_index == self.midi_device_index:
            return
        self.midi_device_index = new_index
        self.save_config()
        self.stop_chord_scanner()
        if new_index >= 0:
            self.start_chord_scanner()
            self.log_message(f"MIDI input set to: {selection}")
        else:
            self.log_message("Chord Scanner disabled.")

    def on_midi_out_changed(self, event=None):
        selection = self.combo_midi_out.get()
        if selection == "Kein MIDI":
            new_index = -1
        else:
            devices = list_midi_out_devices()
            try:
                new_index = devices.index(selection)
            except ValueError:
                return
        if new_index == self.midi_out_device_index:
            return
        self.midi_out_device_index = new_index
        self.save_config()
        self.log_message(f"MIDI output set to: {selection}")

    def start_chord_scanner(self):
        if self.chord_scanner is not None:
            return
        if self.midi_device_index < 0:
            self.log_message("Chord Scanner: Disabled by user.")
            return
        self.chord_scanner = ChordScanner(
            self,
            self.update_chord_display,
            device_index=self.midi_device_index,
            velocity_queue=self.velocity_queue
        )
        self.chord_scanner.start()
        device = self.chord_scanner.get_device_name()
        if device:
            self.log_message(f"Chord Scanner: Ready ({device})")
        else:
            self.log_message("Chord Scanner: Device detected but name unknown.")
        self._chord_scanner_ready = True
        self._try_finish_system_check()

    def stop_chord_scanner(self):
        if self.chord_scanner:
            self.chord_scanner.stop()
            self.chord_scanner = None
        if self.chord_timer:
            self.after_cancel(self.chord_timer)
            self.chord_timer = None
        self.chord_label.config(text="")

    def update_chord_display(self, chord_name):
        if self.chord_timer:
            self.after_cancel(self.chord_timer)
            self.chord_timer = None
        if chord_name:
            self.chord_label.config(text=chord_name)
        else:
            self.chord_timer = self.after(1500, self._clear_chord_label)

    def _clear_chord_label(self):
        self.chord_label.config(text="")
        self.chord_timer = None

    def backup_rpi_performances(self, target_dir, selected_banks=None, callback=None):
        if self.ftp_busy:
            self.log_message("FTP is busy – cannot start backup.")
            if callback:
                self.after(0, callback, False)
            return
        creds = self.get_active_ftp_creds()
        if not creds:
            if callback:
                self.after(0, callback, False)
            return
        self.ftp_busy = True
        def task():
            success = True
            try:
                def ftp_list(ftp):
                    ftp.cwd("/")
                    try: ftp.cwd("SD")
                    except: pass
                    ftp.cwd("performance")
                    folders = []
                    def parse_line(line):
                        line = line.strip()
                        name = ""
                        if "<DIR>" in line:
                            name = line.split("<DIR>", 1)[1].strip()
                        elif line.startswith('d'):
                            parts = line.split(maxsplit=8)
                            if len(parts) == 9:
                                name = parts[8].strip()
                        if name and name not in (".", ".."):
                            folders.append(name)
                    ftp.retrlines('LIST', parse_line)
                    return folders
                all_folders = safe_ftp_operation(creds, ftp_list, self.log_message)
                if selected_banks:
                    folders = [f for f in all_folders if f in selected_banks]
                else:
                    folders = all_folders
                if not folders:
                    self.log_message("No bank folders found on RPi.")
                    success = True
                    return

                def ftp_download(ftp):
                    ftp.cwd("/")
                    try: ftp.cwd("SD")
                    except: pass
                    ftp.cwd("performance")
                    for folder in folders:
                        local_folder = os.path.join(target_dir, folder)
                        os.makedirs(local_folder, exist_ok=True)
                        try:
                            ftp.cwd(folder)
                        except Exception:
                            self.log_message(f"Could not enter {folder} on RPi – aborting backup.")
                            raise
                        files = []
                        def parse_files(line):
                            if ".ini" not in line.lower() or "<DIR>" in line:
                                return
                            line = line.strip()
                            if line.startswith('-'):
                                parts = line.split(maxsplit=8)
                                if len(parts) == 9:
                                    files.append(parts[8].strip())
                            else:
                                parts = line.split(maxsplit=3)
                                if len(parts) == 4:
                                    files.append(parts[3].strip())
                        ftp.retrlines('LIST', parse_files)
                        for file in files:
                            self.log_progress(f" Downloading: {folder}/{file}")
                            local_file = os.path.join(local_folder, file)
                            try:
                                with open(local_file, 'wb') as f:
                                    ftp.retrbinary(f"RETR {file}", f.write)
                            except Exception as e:
                                self.log_message(f"Failed to download {folder}/{file}: {e}")
                                raise
                        ftp.cwd("..")
                        self.clear_progress()
                        self.log_message(f"{folder} backed up ({len(files)} files).")
                safe_ftp_operation(creds, ftp_download, self.log_message)

            except Exception as e:
                self.log_message(f"Backup failed: {e}")
                success = False
            finally:
                self.ftp_busy = False
                if callback:
                    self.after(0, callback, success)

        threading.Thread(target=task, daemon=True).start()

    # -------------------------------------------------------------------------
    # miniDexed configuration (FTP & parser)
    # -------------------------------------------------------------------------
    def on_minidexed_ini_loaded(self, config):
        """
        Empfängt die geparste miniDexed‑Konfiguration (oder None bei Fehler).
        Speichert sie im Cache und aktualisiert das UI.
        """
        if config is not None:
            # Cache im Projekt‑Root ablegen (pc_key_navigation.json)
            cache_file = os.path.join(BASE_DIR, "pc_key_navigation.json")
            try:
                with open(cache_file, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4)
            except Exception:
                pass
            self._apply_minidexed_config(config)
        else:
            # Fallback: Cache laden
            cache_file = os.path.join(BASE_DIR, "pc_key_navigation.json")
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, 'r', encoding='utf-8') as f:
                        cached = json.load(f)
                    self._apply_minidexed_config(cached)
                    self.log_message("Using cached miniDexed configuration.")
                except Exception:
                    self._apply_minidexed_config(None)
            else:
                self._apply_minidexed_config(None)

    def _apply_minidexed_config(self, config):
        self.minidexed_config = config
        if not config:
            self.log_message("MiniDexed configuration not available.")
        self._load_midi_button_mapping()
        self._update_midi_nav_ui()

        if config and hasattr(self, 'volume_slider'):
            vol = config.get("master_volume", 127)
            self.volume_slider.config(command="")
            self.master_volume.set(vol)
            self.volume_slider.config(command=self._on_master_volume_change)
            # Label manuell setzen, da Callback nicht ausgelöst wurde
            if hasattr(self, 'lbl_volume_value'):
                self.lbl_volume_value.config(text=f"{vol:03d}")

    def _update_midi_nav_ui(self):
        """
        Update the status label and automatically enable/disable
        the MIDI button navigation based on the loaded miniDexed configuration.
        """
        if not self.minidexed_config:
            self.lbl_midi_nav_status.config(text="MIDI Button Navigation: (no config)")
            self.btn_midi_config.config(state="disabled")
            self._stop_navigation()
            return

        notes_enabled = self.minidexed_config.get("midi_button_notes", 0) == 1
        if notes_enabled:
            self.lbl_midi_nav_status.config(text="MIDI Button Navigation: ON", fg=COLOR_FG)
            self.btn_midi_config.config(state="normal")
            self._start_navigation()
        else:
            self.lbl_midi_nav_status.config(text="MIDI Button Navigation: OFF", fg=COLOR_FG_DIM)
            self.btn_midi_config.config(state="disabled")
            self._stop_navigation()

        # Update performance select channel label from INI
        if self.minidexed_config:
            psc = self.minidexed_config.get("performance_select_channel", 0)
            self.lbl_perf_channel.config(text=str(psc) if psc > 0 else "–")
        else:
            self.lbl_perf_channel.config(text="?")

    def _load_midi_button_mapping(self):
        """
        Load the saved PC-key → function mapping from midi_button_config.json,
        keep only entries for functions that still exist in the current
        miniDexed configuration.
        """
        mapping_file = os.path.join(BASE_DIR, "midi_button_config.json")
        if not os.path.exists(mapping_file):
            self.midi_button_mapping = {}
            return

        try:
            with open(mapping_file, 'r', encoding='utf-8') as f:
                saved = json.load(f)
        except Exception:
            saved = {}

        valid_functions = {btn["function"] for btn in self.minidexed_config.get("buttons", [])} \
                          if self.minidexed_config else set()

        self.midi_button_mapping = {
            func: keycode
            for func, keycode in saved.items()
            if func in valid_functions
        }

    def open_midi_button_config(self):
        """
        Open the MIDI button configuration dialog.
        After completion, save the new mapping to disk.
        """
        if not self.minidexed_config or not self.minidexed_config.get("buttons"):
            self.log_message("No button functions loaded – cannot configure keys.")
            return

        from harvester.midi_button_config_dialog import MidiButtonConfigDialog

        def on_save(mapping):
            self.midi_button_mapping = mapping
            mapping_file = os.path.join(BASE_DIR, "midi_button_config.json")
            try:
                with open(mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(mapping, f, indent=4)
                self.log_message("MIDI button configuration saved.")
                # If navigation is currently active, restart it to pick up new keys
                if self.midi_handle is not None:
                    self._stop_navigation()
                    self._start_navigation()
            except Exception as e:
                self.log_message(f"Failed to save MIDI button configuration: {e}")

        MidiButtonConfigDialog(self, self.minidexed_config["buttons"],
                               self.midi_button_mapping, on_save)
    # -------------------------------------------------------------------------
    # Controller: enable/disable key events and MIDI handle
    # -------------------------------------------------------------------------
    def _start_navigation(self):
        """Startet den Tastatur‑Hook und öffnet das MIDI‑Handle, falls möglich."""
        if not self.midi_button_mapping:
            self.log_message("No key mapping configured – navigation stays inactive.")
            self._midi_nav_status_reported = True
            self._try_finish_system_check()
            return
        if self.midi_out_device_index < 0:
            self.log_message("No MIDI output device selected – navigation stays inactive.")
            self._midi_nav_status_reported = True
            self._try_finish_system_check()
            return

        already_open = self.midi_handle is not None
        self._open_midi_handle()

        if self.midi_handle is not None:
            self.bind("<KeyPress>", self._on_controller_key_press)
            self.bind("<KeyRelease>", self._on_controller_key_release)
            if not already_open:   # <-- Protokoll nur, wenn wirklich neu gestartet
                self.log_message("MIDI button navigation activated.")
            self._nav_logged_active = True
        else:
            self._nav_logged_active = False

        self._midi_nav_status_reported = True
        self._try_finish_system_check()

    def _stop_navigation(self):
        """Entfernt den Tastatur‑Hook und schließt das MIDI‑Handle."""
        self.unbind("<KeyPress>")
        self.unbind("<KeyRelease>")
        self._close_midi_handle()
        self._nav_logged_active = False   # Reset, damit beim nächsten Start wieder geloggt wird
        self.log_message("MIDI button navigation deactivated.")
        self._midi_nav_status_reported = True
        self._try_finish_system_check()

    def _open_midi_handle(self):
        """Open the MIDI output device and keep the handle for the controller."""
        if self.midi_handle is not None:
            return
        if self.midi_out_device_index < 0:
            self.log_message("No MIDI output device selected – controller disabled.")
            return
        handle = wintypes.HANDLE()
        result = winmm.midiOutOpen(ctypes.byref(handle), self.midi_out_device_index, 0, 0, 0)
        if result != 0:   # MMSYSERR_NOERROR = 0
            self.log_message(f"Failed to open MIDI device (error {result}). Controller disabled.")
            return
        self.midi_handle = handle

    def _close_midi_handle(self):
        """Close the MIDI handle and clean up."""
        if self.midi_handle is not None:
            winmm.midiOutClose(self.midi_handle)
            self.midi_handle = None
            self.active_nav_pressed.clear()

    # -------------------------------------------------------------------------
    # Controller: key event handlers
    # -------------------------------------------------------------------------
    def _on_controller_key_press(self, event):
        """
        Handle KeyPress events when MIDI button navigation is active.
        Only process events if focus is not on an input widget.
        """
        # Ignore if focus is on an input widget (Entry, Text, Spinbox)
        focus = self.focus_get()
        if focus is not None and isinstance(focus, (tk.Entry, tk.Text, tk.Spinbox)):
            return

        # Ignore modifier-only presses
        if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R",
                            "Alt_L", "Alt_R", "Win_L", "Win_R", "Caps_Lock"):
            return

        kc = event.keycode

        # --- Program change buffer ---
        psc = self.minidexed_config.get("performance_select_channel", 0) if self.minidexed_config else 0
        if psc > 0:
            if event.keysym == "Return" and self.prog_buffer:
                try:
                    prog = int(self.prog_buffer)
                    if 1 <= prog <= 128:
                        self._send_controller_program_change(psc, prog - 1)
                        self.log_message(f'Prg Chg: {prog:03d}')
                    self.prog_buffer = ""
                except ValueError:
                    self.prog_buffer = ""
                return

            if event.keysym == "BackSpace":
                self.prog_buffer = self.prog_buffer[:-1]
                return

            if event.keysym == "Escape":
                self.prog_buffer = ""
                return

            if event.char and event.char.isdigit() and len(self.prog_buffer) < 3:
                self.prog_buffer += event.char
                return

            # If we collected digits and now another key is pressed, clear buffer
            if self.prog_buffer:
                self.prog_buffer = ""

        # --- Navigation: look up keycode in mapping ---
        if self.midi_button_mapping and kc in self.midi_button_mapping.values():
            for func, mapped_kc in self.midi_button_mapping.items():
                if mapped_kc == kc and kc not in self.active_nav_pressed:
                    self.active_nav_pressed.add(kc)
                    note = self._get_note_for_function(func)
                    if note is not None:
                        self._send_controller_note_on(note)
                    break

    def _on_controller_key_release(self, event):
        """Handle KeyRelease events – send Note Off."""
        kc = event.keycode
        if kc in self.active_nav_pressed:
            self.active_nav_pressed.discard(kc)
            for func, mapped_kc in self.midi_button_mapping.items():
                if mapped_kc == kc:
                    note = self._get_note_for_function(func)
                    if note is not None:
                        self._send_controller_note_off(note)
                    break

    def _get_note_for_function(self, func_name):
        """Return the MIDI note number for a given function name from the config."""
        if not self.minidexed_config:
            return None
        for btn in self.minidexed_config.get("buttons", []):
            if btn["function"] == func_name:
                return btn["note"]
        return None

    # -------------------------------------------------------------------------
    # Controller: MIDI sending via open handle
    # -------------------------------------------------------------------------
    def _send_controller_note_on(self, note):
        """Send Note On via the open MIDI handle (velocity=1)."""
        if self.midi_handle is None:
            return
        ch = self.minidexed_config.get("midi_button_ch", 1) if self.minidexed_config else 1
        if ch == 0:
            return
        msg = 0x90 | (ch - 1) | (note << 8) | (1 << 16)   # velocity = 1
        try:
            winmm.midiOutShortMsg(self.midi_handle, msg)
        except Exception as e:
            self.log_message(f"MIDI Note On error: {e}")

    def _send_controller_note_off(self, note):
        """Send Note Off via the open MIDI handle."""
        if self.midi_handle is None:
            return
        ch = self.minidexed_config.get("midi_button_ch", 1) if self.minidexed_config else 1
        if ch == 0:
            return
        msg = 0x80 | (ch - 1) | (note << 8)
        try:
            winmm.midiOutShortMsg(self.midi_handle, msg)
        except Exception as e:
            self.log_message(f"MIDI Note Off error: {e}")

    def _send_controller_program_change(self, channel, program):
        """Send Program Change via the open MIDI handle."""
        if self.midi_handle is None:
            return
        msg = 0xC0 | (channel - 1) | (program << 8)
        try:
            winmm.midiOutShortMsg(self.midi_handle, msg)
        except Exception as e:
            self.log_message(f"MIDI Program Change error: {e}")
            
    def _send_controller_bank_select(self, bank):
        """Sendet Bank Select (CC0+CC32) über das offene MIDI‑Handle."""
        if self.midi_handle is None or self.minidexed_config is None:
            return
        ch = self.minidexed_config.get("performance_select_channel", 0)
        if ch <= 0:
            self.log_message("No PerformanceSelectChannel configured – bank select skipped.")
            return
        msb = (bank >> 7) & 0x7F
        lsb = bank & 0x7F
        cc_status = 0xB0 | (ch - 1)
        try:
            winmm.midiOutShortMsg(self.midi_handle, cc_status | (0 << 8) | (msb << 16))
            winmm.midiOutShortMsg(self.midi_handle, cc_status | (32 << 8) | (lsb << 16))
        except Exception as e:
            self.log_message(f"Bank Select error: {e}")

    def _on_master_volume_change(self, value):
        """
        Send Master Volume SysEx when the slider is moved.
        Value is a string from tk.Scale; we convert to int.
        SysEx: F0 7F 7F 04 01 ll mm F7  (ll ignored, set to 0)
        """
        try:
            vol = int(value)
        except ValueError:
            return
        if hasattr(self, 'lbl_volume_value'):
            self.lbl_volume_value.config(text=f"{vol:03d}")
        sysex = [0xF0, 0x7F, 0x7F, 0x04, 0x01, 0x00, vol & 0x7F, 0xF7]

        if self.midi_out_device_index >= 0:
            try:
                from harvester.midi_utils import send_sysex
                send_sysex(self.midi_out_device_index, sysex)
            except Exception as e:
                self.log_message(f"Master Volume SysEx failed: {e}")
    def _sync_histogram_size(self):
        """Passt die Größe des Velocity‑Histogramms an den Chord‑Scanner an."""
        if not hasattr(self, 'chord_frame') or not hasattr(self, 'velocity_histogram'):
            return
        self.chord_frame.update_idletasks()
        chord_width = self.chord_frame.winfo_reqwidth()
        chord_height = self.chord_frame.winfo_reqheight()

        if chord_width > 10 and chord_height > 10:
            self.velocity_histogram.set_dimensions(chord_width, chord_height)    
    # -------------------------------------------------------------------------
    # Cleanup on exit
    # -------------------------------------------------------------------------
    def destroy(self):
        """Clean up MIDI handle before closing."""
        self._close_midi_handle()
        super().destroy()

# =============================================================================
# --- START-ROUTINE ---
# =============================================================================
if __name__ == "__main__":
    app = Harvester()
    app.mainloop()