
# harvester/dialogs.py
import tkinter as tk
from tkinter import messagebox
from harvester.constants import *

class ProfileManager(tk.Toplevel):
    def __init__(self, parent, ftp_data_ref, save_ftp_callback, update_dropdown_callback,
                 default_user=DEFAULT_FTP_USER, default_pass=DEFAULT_FTP_PASS):
        super().__init__(parent)
        self.ftp_data = ftp_data_ref
        self.save_ftp = save_ftp_callback
        self.update_dropdown = update_dropdown_callback
        self.default_user = default_user
        self.default_pass = default_pass
        self.title("Edit Profiles")

        scale = parent.scale
        w = int(320 * scale)
        h = int(320 * scale)
        self.geometry(f"{w}x{h}")
        self.grab_set()
        self.configure(bg=COLOR_BG)

        self.listbox = tk.Listbox(self, height=8, bg=COLOR_BG, fg=COLOR_FG, selectbackground=COLOR_BG_SELECT)
        self.listbox.pack(fill="x", padx=10, pady=10)
        self.listbox.bind('<<ListboxSelect>>', self.on_select)

        frame_fields = tk.Frame(self, bg=COLOR_BG)
        frame_fields.pack(fill="x", padx=10)
        
        tk.Label(frame_fields, text="Profile name:", bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).grid(row=0, column=0, sticky="w")
        self.ent_name = tk.Entry(frame_fields, width=30, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.ent_name.grid(row=0, column=1, pady=2)

        tk.Label(frame_fields, text="IP:", bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).grid(row=1, column=0, sticky="w")
        self.ent_ip = tk.Entry(frame_fields, width=30, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.ent_ip.grid(row=1, column=1, pady=2)

        tk.Label(frame_fields, text="User:", bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).grid(row=2, column=0, sticky="w")
        self.ent_user = tk.Entry(frame_fields, width=30, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.ent_user.grid(row=2, column=1, pady=2)
        self.ent_user.insert(0, self.default_user)

        tk.Label(frame_fields, text="Password:", bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).grid(row=3, column=0, sticky="w")
        self.ent_pass = tk.Entry(frame_fields, width=30, bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG, font=FONT_NORMAL)
        self.ent_pass.grid(row=3, column=1, pady=2)
        self.ent_pass.insert(0, self.default_pass)

        frame_btn = tk.Frame(self, bg=COLOR_BG)
        frame_btn.pack(pady=10)
        btn_style = {"bg": COLOR_BG_BUTTON, "fg": COLOR_FG, "activebackground": COLOR_BG_SELECT, 
                     "activeforeground": COLOR_FG, "font": FONT_NORMAL, "relief": "raised"}
        tk.Button(frame_btn, text="Save/New", command=self.save_profile, **btn_style).pack(side="left", padx=5)
        tk.Button(frame_btn, text="Delete", command=self.delete_profile, **btn_style).pack(side="left", padx=5)

        self.refresh_list()

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.ftp_data.get("profiles", {}).keys():
            self.listbox.insert(tk.END, p)

    def on_select(self, event):
        if not self.listbox.curselection(): return
        name = self.listbox.get(self.listbox.curselection())
        prof = self.ftp_data["profiles"][name]
        self.ent_name.delete(0, tk.END); self.ent_name.insert(0, name)
        self.ent_ip.delete(0, tk.END); self.ent_ip.insert(0, prof.get("ip", ""))
        self.ent_user.delete(0, tk.END); self.ent_user.insert(0, prof.get("user", ""))
        self.ent_pass.delete(0, tk.END); self.ent_pass.insert(0, prof.get("password", ""))

    def save_profile(self):
        name = self.ent_name.get().strip()
        if not name: 
            return
        if "profiles" not in self.ftp_data:
            self.ftp_data["profiles"] = {}
        self.ftp_data["profiles"][name] = {
            "ip": self.ent_ip.get().strip(),
            "user": self.ent_user.get().strip(),
            "password": self.ent_pass.get().strip(),
            "pi_type": "Auto"
        }
        self.save_ftp()
        self.refresh_list()
        self.update_dropdown()

    def delete_profile(self):
        name = self.ent_name.get().strip()
        if name in self.ftp_data.get("profiles", {}):
            del self.ftp_data["profiles"][name]
            self.save_ftp()
            self.refresh_list()
            self.update_dropdown()

class ImportDialog(tk.Toplevel):
    def __init__(self, parent, folders, callback):
        super().__init__(parent)
        self.callback = callback
        self.folders = folders
        self.selected_folders = set()
        self.title("Folder Selection")

        scale = parent.scale
        w = int(350 * scale)
        h = int(520 * scale)            # etwas höher wegen der Checkbox
        self.geometry(f"{w}x{h}")
        self.grab_set()
        self.configure(bg=COLOR_BG)

        header_frame = tk.Frame(self, bg=COLOR_BG, pady=10)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="RPi Import Selection", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG).pack()
        tk.Label(header_frame, text="Click to toggle:", font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG).pack()

        frame = tk.Frame(self, bg=COLOR_BG)
        frame.pack(fill="both", expand=True, padx=15, pady=5)

        self.listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=FONT_NORMAL,
                                  bg=COLOR_BG, fg=COLOR_FG, relief="flat",
                                  selectbackground=COLOR_BG_SELECT, selectforeground=COLOR_FG,
                                  highlightthickness=1, highlightcolor=COLOR_FG, highlightbackground=COLOR_FG_DIM)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(frame, orient="vertical", command=self.listbox.yview, bg=COLOR_BG)
        scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.bind("<ButtonRelease-1>", self.toggle_item)
        self.refresh_list()

        # --- NEU: Checkbox zum Leeren des Import-Ordners ---
        check_frame = tk.Frame(self, bg=COLOR_BG)
        check_frame.pack(fill="x", padx=15, pady=(5, 0))
        self.delete_all_var = tk.BooleanVar(value=False)
        cb = tk.Checkbutton(check_frame, text="Delete Import Folder before download",
                            variable=self.delete_all_var,
                            bg=COLOR_BG, fg=COLOR_FG, selectcolor=COLOR_BG,
                            activebackground=COLOR_BG, font=FONT_NORMAL)
        cb.pack(anchor="w")

        action_frame = tk.Frame(self, bg=COLOR_BG)
        action_frame.pack(fill="x", padx=15, pady=(5, 10))
        btn_style = {"font": FONT_NORMAL, "bg": COLOR_BG_BUTTON, "fg": COLOR_FG,
                     "activebackground": COLOR_BG_SELECT, "activeforeground": COLOR_FG,
                     "relief": "raised", "cursor": "hand2"}
        tk.Button(action_frame, text="[X] All", command=self.select_all, **btn_style).pack(side="left", fill="x", expand=True, padx=(0, 3))
        tk.Button(action_frame, text="[ ] None", command=self.select_none, **btn_style).pack(side="left", fill="x", expand=True, padx=(3, 0))
        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))
        tk.Button(btn_frame, text="> Import", command=self.on_ok, **btn_style).pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(btn_frame, text="> Cancel", command=self.on_cancel, **btn_style).pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for f in self.folders:
            prefix = "[X]  " if f in self.selected_folders else "[ ]  "
            self.listbox.insert(tk.END, prefix + f)

    def toggle_item(self, event):
        selection = self.listbox.curselection()
        if not selection: return
        index = selection[0]
        folder = self.folders[index]
        if folder in self.selected_folders:
            self.selected_folders.remove(folder)
        else:
            self.selected_folders.add(folder)
        self.refresh_list()
        self.listbox.selection_set(index) 

    def select_all(self):
        self.selected_folders = set(self.folders)
        self.refresh_list()

    def select_none(self):
        self.selected_folders.clear()
        self.refresh_list()

    def on_ok(self):
        self.destroy()
        # Callback übergibt jetzt auch den Checkbox-Status
        self.callback(sorted(list(self.selected_folders)), self.delete_all_var.get())

    def on_cancel(self):
        self.destroy()
        self.callback([])

class PiCleanupDialog(tk.Toplevel):
    def __init__(self, parent, folders, callback):
        super().__init__(parent)
        self.title("RPi Backup Cleanup")
        scale = parent.scale
        w = int(350 * scale)
        h = int(480 * scale)
        self.geometry(f"{w}x{h}")
        self.grab_set()
        self.callback = callback
        self.folders = sorted(folders)
        self.selected_folders = set()
        self.configure(bg=COLOR_BG)
        
        header_frame = tk.Frame(self, bg=COLOR_BG, pady=10)
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="Delete RPi Backups", font=FONT_TITLE, bg=COLOR_BG, fg=COLOR_FG_WARN).pack()
        tk.Label(header_frame, text="Click to select:", font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG).pack()
        
        frame = tk.Frame(self, bg=COLOR_BG)
        frame.pack(fill="both", expand=True, padx=15, pady=5)
        
        self.listbox = tk.Listbox(frame, selectmode=tk.SINGLE, font=FONT_NORMAL, 
                                  bg=COLOR_BG, fg=COLOR_FG, relief="flat", 
                                  selectbackground="#662222", selectforeground=COLOR_FG_WARN,
                                  highlightthickness=1, highlightcolor=COLOR_FG, highlightbackground=COLOR_FG_DIM)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(frame, orient="vertical", command=self.listbox.yview, bg=COLOR_BG)
        scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.bind("<ButtonRelease-1>", self.toggle_item)
        self.refresh_list()
            
        action_frame = tk.Frame(self, bg=COLOR_BG)
        action_frame.pack(fill="x", padx=15, pady=(5, 10))
        btn_style = {"font": FONT_NORMAL, "bg": COLOR_BG_BUTTON, "fg": COLOR_FG, 
                     "activebackground": COLOR_BG_SELECT, "activeforeground": COLOR_FG, 
                     "relief": "raised", "cursor": "hand2"}
        btn_style_warn = {"font": FONT_NORMAL, "bg": COLOR_BG_BUTTON, "fg": COLOR_FG_WARN, 
                          "activebackground": "#442222", "activeforeground": COLOR_FG_WARN, 
                          "relief": "raised", "cursor": "hand2"}
        tk.Button(action_frame, text="[X] All", command=self.select_all, **btn_style).pack(side="left", fill="x", expand=True, padx=(0, 3))
        tk.Button(action_frame, text="[ ] None", command=self.select_none, **btn_style).pack(side="left", fill="x", expand=True, padx=(3, 0))
        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.pack(fill="x", padx=15, pady=(0, 15))
        tk.Button(btn_frame, text="🗑️ Delete", command=self.on_ok, **btn_style_warn).pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(btn_frame, text="> Cancel", command=self.on_cancel, **btn_style).pack(side="left", fill="x", expand=True, padx=(5, 0))
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for f in self.folders:
            prefix = "[X]  " if f in self.selected_folders else "[ ]  "
            self.listbox.insert(tk.END, prefix + f)

    def toggle_item(self, event):
        selection = self.listbox.curselection()
        if not selection: return
        index = selection[0]
        folder = self.folders[index]
        if folder in self.selected_folders: self.selected_folders.remove(folder)
        else: self.selected_folders.add(folder)
        self.refresh_list()
        self.listbox.selection_set(index) 

    def select_all(self):
        self.selected_folders = set(self.folders)
        self.refresh_list()

    def select_none(self):
        self.selected_folders.clear()
        self.refresh_list()

    def on_ok(self):
        self.destroy()
        self.callback(sorted(list(self.selected_folders)))

    def on_cancel(self):
        self.destroy()
        self.callback([])
