# harvester/about_dialog.py
import tkinter as tk
import webbrowser
import os
from PIL import Image, ImageTk
from .constants import (SCALE_FACTOR, COLOR_BG, COLOR_FG, COLOR_BG_BUTTON,
                        COLOR_BG_SELECT, FONT_NORMAL, FONT_SMALL, COLOR_FG_DIM)

# HIER DIE ZENTRALEN VARIABLEN FÜR DEN WORKFLOW
VERSION = "0.2.10"
VERSION_DATE = "2026/07/19"

def show_about(parent, base_dir):
    """Open a small info window with logo and version information.
    The window is 20% larger than the content to give it some breathing room."""
    win = tk.Toplevel(parent)
    win.title("About DreamDexed Studio")
    win.configure(bg=COLOR_BG)
    win.resizable(False, False)
    win.grab_set()   # modal

    # Load larger logo (if available)
    logo_path = os.path.join(base_dir, "harvester", "logo.png")
    if os.path.exists(logo_path):
        pil_image = Image.open(logo_path)
        target_height = int(100 * SCALE_FACTOR)
        aspect = pil_image.width / pil_image.height
        target_width = int(target_height * aspect)
        pil_image = pil_image.resize((target_width, target_height), Image.LANCZOS)
        logo_tk = ImageTk.PhotoImage(pil_image)
        lbl_img = tk.Label(win, image=logo_tk, bg=COLOR_BG)
        lbl_img.image = logo_tk   # keep reference
        lbl_img.pack(pady=(20, 10))

    # Text lines (Nutzen jetzt die Variablen von oben)
    lines = [
        "© 2026 by Soundplantage - Banana71",
        f"Version {VERSION} - {VERSION_DATE}",
        "This software is released under the MIT License.",
    ]
    for line in lines:
        tk.Label(win, text=line, font=FONT_NORMAL, fg="white", bg=COLOR_BG).pack()

    # Links (clickable labels)
    def open_url(url):
        webbrowser.open(url)

    link_frame = tk.Frame(win, bg=COLOR_BG)
    link_frame.pack(pady=10)

    # HERVORGEHOBENER LINK ZUR EIGENEN PROJEKTSEITE (vorrangig, weiße Schrift)
    lbl_project = tk.Label(link_frame,
                           text="https://github.com/Banana71/DreamDexed-Studio",
                           font=FONT_NORMAL, fg=COLOR_FG, bg=COLOR_BG, cursor="hand2")
    lbl_project.pack(pady=(0, 5))
    lbl_project.bind("<Button-1>", lambda e: open_url("https://github.com/Banana71/DreamDexed-Studio"))

    # Weitere Links (abgedunkelt)
    lbl1 = tk.Label(link_frame, text="https://github.com/probonopd/MiniDexed",
                    font=FONT_NORMAL, fg="white", bg=COLOR_BG, cursor="hand2")
    lbl1.pack()
    lbl1.bind("<Button-1>", lambda e: open_url("https://github.com/probonopd/MiniDexed"))

    lbl2 = tk.Label(link_frame, text="https://github.com/DreamDexed/DreamDexed",
                    font=FONT_NORMAL, fg="white", bg=COLOR_BG, cursor="hand2")
    lbl2.pack()
    lbl2.bind("<Button-1>", lambda e: open_url("https://github.com/DreamDexed/DreamDexed"))

    # Close button
    tk.Button(win, text="Close", command=win.destroy, bg=COLOR_BG_BUTTON, fg=COLOR_FG,
              activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
              font=FONT_NORMAL, relief="raised", cursor="hand2").pack(pady=10)

    win.update_idletasks()
    req_w = win.winfo_reqwidth()
    req_h = win.winfo_reqheight()
    new_w = int(req_w * 1.2)
    new_h = int(req_h * 1.05)
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (new_w // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (new_h // 2)
    win.geometry(f"{new_w}x{new_h}+{x}+{y}")