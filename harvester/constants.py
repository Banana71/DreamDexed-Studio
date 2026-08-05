# harvester/constants.py
import tkinter as tk
import os
import configparser

# ----------------------------------------------------------------------
# GUI‑Skalierungsfaktor aus config.ini lesen (Standard 100 %)
# ----------------------------------------------------------------------
def _read_gui_scale_percent():
    """Liest den Prozentwert aus [GUI] gui_scale_percent,
       berechnet den multiplikativen Faktor (Wert/100) und gibt ihn zurück."""
    config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                               'config.ini')
    if os.path.exists(config_path):
        cfg = configparser.ConfigParser()
        cfg.read(config_path, encoding='utf-8')
        try:
            percent = cfg.getint('GUI', 'gui_scale_percent', fallback=100)
        except Exception:
            percent = 100
        percent = max(75, min(300, percent))   # Sicherheitsbereich
        return percent / 100.0
    return 1.0

_GUI_SCALE = _read_gui_scale_percent()

def get_scaling_factor(reference_height=1080):
    root = tk.Tk()
    root.withdraw()
    height = root.winfo_screenheight()
    root.destroy()
    auto_factor = height / reference_height
    return max(0.4, min(2.5, auto_factor * _GUI_SCALE))

SCALE_FACTOR = get_scaling_factor()

def scaled_font(base_size=9):
    return ("Segoe UI", int(base_size * SCALE_FACTOR))

# ----------------------------------------------------------------------
# Farben & Schriften (Retro-Theme)
# ----------------------------------------------------------------------
COLOR_BG           = "#221d16"
COLOR_FG           = "#48e0d0"   # "#48e0d0"
COLOR_FG_DIM       = "#B0C1E7"
COLOR_FG_WARN      = "#F59300"
COLOR_BG_SELECT    = "#0E8585" 
COLOR_BG_BUTTON    = "#1a1a1a"
COLOR_BG_ENTRY     = "#221d16"
COLOR_BG_TOOLTIP   = "#237070"
COLOR_WORKFLOW     = "#2a4a3f"
COLOR_FG_CHORD     = "#FF7B23"
COLOR_BG_CHORD     = "#42210A"
COLOR_VELOCITY_BAR = "#FF7B23"  # "#00ffdd"
COLOR_BG_SLIDER    = "#3F3939"
FONT_FAMILY        = "Segoe UI"

FONT_NORMAL   = scaled_font(10)
FONT_SMALL    = scaled_font(9)
FONT_BOLD     = (FONT_FAMILY, int(10 * SCALE_FACTOR), "bold")
FONT_TITLE    = (FONT_FAMILY, int(12 * SCALE_FACTOR), "bold")
CHORD_FONT_FAMILY = "DOTO Black"
CHORD_FONT_SIZE   = 18     # Basisgröße bei 100 % Skalierung
# ----------------------------------------------------------------------
# Pfade und Standard-Credentials
# ----------------------------------------------------------------------
PERF_IMPORT = 'Import/performance'
EXPORT_DIR_NAME = 'Export'

DEFAULT_FTP_USER = "admin"
DEFAULT_FTP_PASS = "admin"

# ----------------------------------------------------------------------
# Default MIDI button mapping (PC key names as displayed to the user)
# ----------------------------------------------------------------------
DEFAULT_MIDI_BUTTON_MAP = {
    "Prev":     "Arrow left",
    "Next":     "Arrow right",
    "Select":   "Arrow up",
    "Back":     "Arrow down",
    "Home":     "Home button",
    "PgmUp":    "Num +",
    "PgmDown":  "Num -",
    "BankUp":   "Page up",
    "BankDown": "Page Down",
    "TGUp":     "Num *",
    "TGDown":   "Num /",
}