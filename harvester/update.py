# harvester/update.py
import tkinter as tk
from tkinter import messagebox
import threading
import requests
import io
import zipfile
import os
import re
import shutil
from datetime import datetime
from harvester.constants import *
from harvester.ftp_utils import safe_ftp_operation
from harvester.widgets import ToolTip   # NEU

GITHUB_API_TREES = "https://api.github.com/repos/Banana71/Soundplantage/git/trees/main?recursive=1"
ZIP_URL = "https://github.com/Banana71/Soundplantage/archive/refs/heads/main.zip"
PDF_FILENAME = "Performance List.pdf"
REPO_PREFIX = "Soundplantage-main/"


class UpdateDialog(tk.Toplevel):
    def __init__(self, parent, creds, harvester):
        super().__init__(parent)
        self.harvester = harvester
        self.creds = creds
        self.sp_root = os.path.join(harvester.entry_base_path.get(), "Soundplantage", "performance")
        self.pdf_content = None
        self.rpi_banks = {}
        self.sp_banks = {}
        self.last_download = "unknown"
        self.selected_rpi_banks = set()
        self.update_prepared = False

        self.warning_accepted = self.harvester.config.getboolean('Update', 'warning_accepted', fallback=False)
        self.warning_var = tk.BooleanVar(value=self.warning_accepted)

        self.title("Soundplantage Update")
        self.configure(bg=COLOR_BG)
        self.resizable(False, False)

        scale = self.harvester.scale
        w = int(600 * scale)
        h = int(750 * scale)
        self.geometry(f"{w}x{h}")

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        x = px + pw - w -8
        y = py -30
        #if y < 0:
        #    y = py
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.grab_set()
        self.build_gui()

        self._load_existing_sp_data()
        self.listbox_rpi.insert(tk.END, "Loading banks from RPi...")
        threading.Thread(target=self._fetch_rpi_bank_list, daemon=True).start()

    # -------------------------------------------------------------------------
    # GUI
    # -------------------------------------------------------------------------
    def build_gui(self):
        # Header
        tk.Label(self, text="Soundplantage Update", font=FONT_BOLD,
                 bg=COLOR_BG, fg=COLOR_FG).pack(pady=10)

        # Warntext und Checkbox
        warn_frame = tk.Frame(self, bg=COLOR_BG)
        warn_frame.pack(fill="x", padx=10, pady=(0, 5))
        warn_text = ("⚠️ Important:\n"
                     "Updates will overwrite modified performances on the Raspberry Pi.\n"
                     "User‑customized performances should be stored in a separate bank\n"
                     "(use the RPi Explorer to create banks and copy performances with F3).\n"
                     "Only banks selected on the right side will be affected.")
        tk.Label(warn_frame, text=warn_text, font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG_WARN,
                 justify="center", wraplength=600).pack(anchor="center", pady=5)
        self.chk_warning = tk.Checkbutton(warn_frame, text="I understand – enable update buttons",
                                          variable=self.warning_var, bg=COLOR_BG, fg=COLOR_FG,
                                          selectcolor=COLOR_BG, activebackground=COLOR_BG,
                                          activeforeground=COLOR_FG, font=FONT_SMALL,
                                          command=self._on_warning_changed)
        self.chk_warning.pack(anchor="center", pady=(5, 0))

        main_frame = tk.Frame(self, bg=COLOR_BG)
        main_frame.pack(fill="both", expand=True, padx=10, pady=5)

        # Linke Spalte
        left_frame = tk.Frame(main_frame, bg=COLOR_BG, width=int(290 * self.harvester.scale),
                              height=int(400 * self.harvester.scale))
        left_frame.pack(side="left", padx=(0, 5), fill="both")
        left_frame.pack_propagate(False)

        tk.Label(left_frame, text="Soundplantage (GitHub)", font=FONT_BOLD,
                 bg=COLOR_BG, fg=COLOR_FG).pack(anchor="w")
        self.lbl_last_dl = tk.Label(left_frame, text="Last download: unknown", font=FONT_SMALL,
                                    bg=COLOR_BG, fg=COLOR_FG_DIM)
        self.lbl_last_dl.pack(anchor="w")

        self.listbox_sp = tk.Listbox(left_frame, width=30, height=14, font=FONT_NORMAL,
                                     bg=COLOR_BG, fg=COLOR_FG, relief="flat",
                                     selectbackground=COLOR_BG_SELECT, selectforeground=COLOR_FG,
                                     highlightthickness=1, highlightcolor=COLOR_FG,
                                     highlightbackground=COLOR_FG_DIM)
        self.listbox_sp.pack(fill="both", expand=True)
        scroll_sp = tk.Scrollbar(self.listbox_sp, orient="vertical", command=self.listbox_sp.yview, bg=COLOR_BG)
        scroll_sp.pack(side="right", fill="y")
        self.listbox_sp.config(yscrollcommand=scroll_sp.set)

        # Button-Leiste unter der linken Listbox (NEU)
        sp_btn_frame = tk.Frame(left_frame, bg=COLOR_BG)
        sp_btn_frame.pack(pady=(5, 0))

        btn_refresh = tk.Button(sp_btn_frame, text="Refresh from GitHub",
                                font=FONT_SMALL, bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                                activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
                                relief="raised", cursor="hand2",
                                command=self._manual_refresh_github)
        btn_refresh.pack(side="left", padx=(0, 5))

        self.btn_copy_to_rpi = tk.Button(sp_btn_frame, text="Copy to RPi",
                                         font=FONT_SMALL, bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                                         activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
                                         relief="raised", cursor="hand2")
        self.btn_copy_to_rpi.pack(side="left")
        ToolTip(self.btn_copy_to_rpi, "Copy selected bank to RPi (overwrites existing) Hold for 2s. For safe update use right side.")

        # Halte-Logik für Copy-Button
        self._copy_timer = None
        self.btn_copy_to_rpi.bind("<ButtonPress-1>", self._on_copy_press)
        self.btn_copy_to_rpi.bind("<ButtonRelease-1>", self._on_copy_release)
        self.btn_copy_to_rpi.bind("<Leave>", self._on_copy_release, add='+')

        tk.Label(left_frame, text="", font=FONT_SMALL, bg=COLOR_BG).pack()

        # Rechte Spalte
        right_frame = tk.Frame(main_frame, bg=COLOR_BG, width=int(290 * self.harvester.scale),
                               height=int(400 * self.harvester.scale))
        right_frame.pack(side="left", padx=(5, 0), fill="both")
        right_frame.pack_propagate(False)

        profile = self.harvester.get_current_profile_name()
        tk.Label(right_frame, text=f"RPi - {profile}", font=FONT_BOLD,
                 bg=COLOR_BG, fg=COLOR_FG).pack(anchor="w")
        tk.Label(right_frame, text="", font=FONT_SMALL, bg=COLOR_BG).pack()

        self.listbox_rpi = tk.Listbox(right_frame, selectmode=tk.SINGLE, width=30, height=14,
                                      font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG, relief="flat",
                                      selectbackground=COLOR_BG_SELECT, selectforeground=COLOR_FG,
                                      highlightthickness=1, highlightcolor=COLOR_FG,
                                      highlightbackground=COLOR_FG_DIM)
        self.listbox_rpi.pack(fill="both", expand=True)
        scroll_rpi = tk.Scrollbar(self.listbox_rpi, orient="vertical", command=self.listbox_rpi.yview, bg=COLOR_BG)
        scroll_rpi.pack(side="right", fill="y")
        self.listbox_rpi.config(yscrollcommand=scroll_rpi.set)
        self.listbox_rpi.bind("<ButtonRelease-1>", self._toggle_rpi_item)

        rpi_btn_frame1 = tk.Frame(right_frame, bg=COLOR_BG)
        rpi_btn_frame1.pack(fill="x", pady=(5, 0))
        tk.Button(rpi_btn_frame1, text="[X] All", command=self._select_all_rpi,
                  font=FONT_SMALL, bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                  activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
                  relief="raised", cursor="hand2").pack(side="left", padx=2)
        tk.Button(rpi_btn_frame1, text="[ ] None", command=self._select_none_rpi,
                  font=FONT_SMALL, bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                  activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
                  relief="raised", cursor="hand2").pack(side="left", padx=2)
        self.btn_prepare = tk.Button(rpi_btn_frame1, text="Prepare Update",
                                     font=FONT_SMALL, bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                                     activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
                                     relief="raised", cursor="hand2",
                                     command=self.start_update)
        self.btn_prepare.pack(side="left", padx=10)

        self.btn_apply = tk.Button(right_frame, text="Start Update",
                                   font=FONT_SMALL, bg=COLOR_BG_SELECT, fg=COLOR_FG_DIM,
                                   activebackground=COLOR_BG_BUTTON, activeforeground=COLOR_FG,
                                   relief="raised", cursor="hand2",
                                   command=self.apply_update_to_rpi)
        self.btn_apply.pack(pady=(5, 0), fill="x")
        self.btn_apply.config(state=tk.DISABLED)

        self._update_buttons_state()

    # -------------------------------------------------------------------------
    # Warnhinweis-Checkbox
    # -------------------------------------------------------------------------
    def _on_warning_changed(self):
        accepted = self.warning_var.get()
        if not self.harvester.config.has_section('Update'):
            self.harvester.config.add_section('Update')
        self.harvester.config.set('Update', 'warning_accepted', str(int(accepted)))
        try:
            with open(os.path.join(self.harvester.entry_base_path.get(), 'config.ini'), 'w', encoding='utf-8') as f:
                self.harvester.config.write(f)
        except Exception as e:
            self.harvester.log_message(f"❌ Could not save warning setting: {e}")
        self._update_buttons_state()

    def _update_buttons_state(self):
        can_prepare = self.warning_var.get() and bool(self.selected_rpi_banks)
        self.btn_prepare.config(state=tk.NORMAL if can_prepare else tk.DISABLED)
        if self.update_prepared and self.warning_var.get():
            self.btn_apply.config(state=tk.NORMAL)
        else:
            self.btn_apply.config(state=tk.DISABLED)

    # -------------------------------------------------------------------------
    # Copy to RPi (NEU – Halte‑Logik)
    # -------------------------------------------------------------------------
    def _on_copy_press(self, event):
        if self.harvester.ftp_busy:
            self.harvester.log_message("⏳ FTP busy – cannot copy now.")
            return
        self.btn_copy_to_rpi.config(text="Hold 2s...", bg=COLOR_BG_SELECT)
        self._copy_timer = self.after(2000, self._execute_copy_to_rpi)

    def _on_copy_release(self, event):
        if self._copy_timer:
            self.after_cancel(self._copy_timer)
            self._copy_timer = None
        self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON)

    def _execute_copy_to_rpi(self):
        self._copy_timer = None
        self.btn_copy_to_rpi.config(text="Copying...", bg=COLOR_BG_SELECT)

        # Ausgewählte Bank aus linker Liste ermitteln
        sel = self.listbox_sp.curselection()
        if not sel:
            self.harvester.log_message("⚠️ No bank selected on the left side.")
            self.btn_copy_to_rpi.after(1000, lambda: self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON))
            return
        bank_entry = self.listbox_sp.get(sel[0])
        bank_name = bank_entry.split(" – ")[0]
        sp_src = os.path.join(self.sp_root, bank_name)
        if not os.path.isdir(sp_src):
            self.harvester.log_message(f"❌ Local bank folder not found: {sp_src}")
            self.btn_copy_to_rpi.after(1000, lambda: self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON))
            return

        base = self.harvester.entry_base_path.get()
        profile = self.harvester.get_current_profile_name()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

        # ── 1. Prüfen, ob die Bank auf dem RPi existiert ──
        def check_and_start():
            try:
                def ftp_check(ftp):
                    ftp.cwd("/SD/performance")
                    try:
                        ftp.cwd(bank_name)
                        return True
                    except Exception:
                        return False
                exists = safe_ftp_operation(self.creds, ftp_check, self.harvester.log_message)
                if exists:
                    # Backup erstellen
                    backup_dir = os.path.join(base, "_backups", profile, f"performance_{timestamp}")
                    os.makedirs(backup_dir, exist_ok=True)
                    self.harvester.log_message(f"📦 Creating backup of bank '{bank_name}' to {backup_dir} …")
                    self.btn_copy_to_rpi.config(text="Backing up...", bg=COLOR_BG_SELECT)

                    self.harvester.backup_rpi_performances(
                        backup_dir,
                        selected_banks=[bank_name],
                        callback=lambda success: self._on_backup_done(success, backup_dir, bank_name, sp_src, timestamp)
                    )
                else:
                    # Keine Bank auf RPi → direkt hochladen
                    self.harvester.log_message(f"📤 Bank '{bank_name}' not on RPi. Uploading new bank.")
                    self._upload_bank(sp_src, bank_name)
            except Exception as e:
                self.harvester.log_message(f"❌ Error during existence check: {e}")
                self.btn_copy_to_rpi.after(1000, lambda: self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON))
        threading.Thread(target=check_and_start, daemon=True).start()

    def _on_backup_done(self, success, backup_dir, bank_name, sp_src, timestamp):
        if not success:
            self.harvester.log_message("❌ Backup failed – copy aborted.")
            self.btn_copy_to_rpi.after(1000, lambda: self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON))
            return
        self.harvester.log_message(f"✅ Backup successful. Removing old bank '{bank_name}' from RPi…")
        self.btn_copy_to_rpi.config(text="Deleting old...", bg=COLOR_BG_SELECT)

        def delete_and_upload():
            try:
                # ── 2. Alte Bank auf RPi löschen ──
                def ftp_delete(ftp):
                    ftp.cwd("/SD/performance")
                    try:
                        ftp.cwd(bank_name)
                        files = []
                        ftp.retrlines('NLST', files.append)
                        num_files = 0
                        for f in files:
                            if f not in ('.', '..'):
                                ftp.delete(f)
                                num_files += 1
                        ftp.cwd("..")
                        ftp.rmd(bank_name)
                        self.harvester.log_message(f"🗑️ Removed bank '{bank_name}' ({num_files} files).")
                    except Exception:
                        pass
                safe_ftp_operation(self.creds, ftp_delete, self.harvester.log_message)

                # ── 3. Neue Bank hochladen ──
                self.harvester.log_message(f"⬆️ Uploading bank '{bank_name}' from Soundplantage…")
                self._upload_bank(sp_src, bank_name)
            except Exception as e:
                self.harvester.log_message(f"❌ Error during delete/upload: {e}")
                self.btn_copy_to_rpi.after(1000, lambda: self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON))
        threading.Thread(target=delete_and_upload, daemon=True).start()

    def _upload_bank(self, sp_src, bank_name):
        """Reiner Upload der Bank von sp_src nach /SD/performance/bank_name"""
        try:
            def ftp_upload(ftp):
                ftp.cwd("/SD/performance")
                try:
                    ftp.mkd(bank_name)
                except Exception:
                    pass
                ftp.cwd(bank_name)
                ini_files = [f for f in os.listdir(sp_src) if f.lower().endswith('.ini')]
                for ini in ini_files:
                    local_file = os.path.join(sp_src, ini)
                    with open(local_file, 'rb') as f:
                        ftp.storbinary(f"STOR {ini}", f)
                    self.harvester.log_progress(f" ⏳ Overwriting {bank_name}/{ini} …")
                self.harvester.clear_progress()
                self.harvester.log_message(f"✅ Bank '{bank_name}' copied to RPi ({len(ini_files)} files).")
            safe_ftp_operation(self.creds, ftp_upload, self.harvester.log_message)
            self.after(0, lambda: self.btn_copy_to_rpi.config(text="Copied!", bg=COLOR_BG_BUTTON))
            self.after(1500, lambda: self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON))
        except Exception as e:
            self.harvester.log_message(f"❌ Upload failed: {e}")
            self.after(0, lambda: self.btn_copy_to_rpi.config(text="Copy to RPi", bg=COLOR_BG_BUTTON))

    # -------------------------------------------------------------------------
    # Auswahllogik rechte Listbox
    # -------------------------------------------------------------------------
    def _select_all_rpi(self):
        self.selected_rpi_banks = set(self.rpi_banks.keys())
        self._refresh_rpi_list()
        self._update_buttons_state()

    def _select_none_rpi(self):
        self.selected_rpi_banks.clear()
        self._refresh_rpi_list()
        self._update_buttons_state()

    def _toggle_rpi_item(self, event):
        sel = self.listbox_rpi.curselection()
        if not sel:
            return
        index = sel[0]
        all_banks = sorted(self.rpi_banks.keys())
        if index >= len(all_banks):
            return
        bank = all_banks[index]
        if bank in self.selected_rpi_banks:
            self.selected_rpi_banks.remove(bank)
        else:
            self.selected_rpi_banks.add(bank)
        self._refresh_rpi_list()
        self.listbox_rpi.selection_set(index)
        self._update_buttons_state()

    def _refresh_rpi_list(self):
        self.listbox_rpi.delete(0, tk.END)
        for bank in sorted(self.rpi_banks.keys()):
            count = self.rpi_banks[bank]
            prefix = "[X]  " if bank in self.selected_rpi_banks else "[ ]  "
            self.listbox_rpi.insert(tk.END, f"{prefix}{bank} – {count} Perf.")

    def _update_rpi_list(self):
        self.selected_rpi_banks.clear()
        self._refresh_rpi_list()
        self._update_buttons_state()

    # -------------------------------------------------------------------------
    # GitHub-Download
    # -------------------------------------------------------------------------
    def _manual_refresh_github(self):
        self.btn_prepare.config(state="disabled")
        self.update_prepared = False
        self._update_buttons_state()
        threading.Thread(target=self._download_from_github, daemon=True).start()

    def _download_from_github(self):
        try:
            resp = requests.get(ZIP_URL, timeout=30)
            resp.raise_for_status()
            zip_data = io.BytesIO(resp.content)
        except Exception as e:
            self.after(0, lambda: self.harvester.log_message(f"Download failed: {e}"))
            return

        if os.path.exists(self.sp_root):
            shutil.rmtree(self.sp_root)
        os.makedirs(self.sp_root, exist_ok=True)

        try:
            with zipfile.ZipFile(zip_data) as zf:
                for name in zf.namelist():
                    if name.startswith(REPO_PREFIX + "performance/") and name.endswith(".ini"):
                        rel_path = name[len(REPO_PREFIX):]
                        target_path = os.path.join(os.path.dirname(self.sp_root), rel_path)
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with open(target_path, 'wb') as f:
                            f.write(zf.read(name))
                pdf_path = f"{REPO_PREFIX}{PDF_FILENAME}"
                try:
                    pdf_target = os.path.join(os.path.dirname(self.sp_root), PDF_FILENAME)
                    with open(pdf_target, 'wb') as f:
                        f.write(zf.read(pdf_path))
                except KeyError:
                    pass

            self.harvester.log_message("✅ Soundplantage download complete.")
            self.after(0, self._update_sp_list)
        except Exception as e:
            self.after(0, lambda: self.harvester.log_message(f"Extraction failed: {e}"))

    def _update_sp_list(self):
        self.sp_banks = {}
        if os.path.isdir(self.sp_root):
            for bank in sorted(os.listdir(self.sp_root)):
                bank_dir = os.path.join(self.sp_root, bank)
                if os.path.isdir(bank_dir):
                    count = len([f for f in os.listdir(bank_dir) if f.lower().endswith('.ini')])
                    self.sp_banks[bank] = count

        self.listbox_sp.delete(0, tk.END)
        for bank, count in self.sp_banks.items():
            self.listbox_sp.insert(tk.END, f"{bank} – {count} Perf.")

        self._update_last_download_label()
        self._update_buttons_state()

    def _update_last_download_label(self):
        latest = 0
        for dirpath, _, filenames in os.walk(self.sp_root):
            for f in filenames:
                if f.lower().endswith('.ini'):
                    mtime = os.path.getmtime(os.path.join(dirpath, f))
                    if mtime > latest:
                        latest = mtime
        if latest > 0:
            self.last_download = datetime.fromtimestamp(latest).strftime('%d.%m.%Y %H:%M')
        else:
            self.last_download = "unknown"
        self.lbl_last_dl.config(text=f"Last download: {self.last_download}")

    def _load_existing_sp_data(self):
        if os.path.isdir(self.sp_root):
            self.sp_banks = {}
            for bank in sorted(os.listdir(self.sp_root)):
                bank_dir = os.path.join(self.sp_root, bank)
                if os.path.isdir(bank_dir):
                    count = len([f for f in os.listdir(bank_dir) if f.lower().endswith('.ini')])
                    self.sp_banks[bank] = count
            self._update_sp_list()

    # -------------------------------------------------------------------------
    # RPi-Bankliste
    # -------------------------------------------------------------------------
    def _fetch_rpi_bank_list(self):
        try:
            def ftp_op(ftp):
                ftp.cwd("/SD/performance")
                lines = []
                ftp.retrlines('LIST', lines.append)
                banks = {}
                for line in lines:
                    line = line.strip()
                    if line.startswith('d') or '<DIR>' in line:
                        parts = line.split()
                        if parts:
                            name = parts[-1]
                            if name not in ('.', '..'):
                                banks[name] = 0
                for bank in banks:
                    try:
                        ftp.cwd(bank)
                        files = []
                        ftp.retrlines('NLST', files.append)
                        banks[bank] = sum(1 for f in files if f.lower().endswith('.ini'))
                        ftp.cwd('..')
                    except Exception:
                        pass
                return banks

            self.rpi_banks = safe_ftp_operation(self.creds, ftp_op, self.harvester.log_message) or {}
            self.harvester.log_message(f"✅ RPi bank list loaded: {len(self.rpi_banks)} banks found.")
            self.after(0, self._update_rpi_list)
        except Exception as e:
            self.after(0, lambda: self.harvester.log_message(f"RPi read failed: {e}"))

    # -------------------------------------------------------------------------
    # Lokaler Update-Vorgang
    # -------------------------------------------------------------------------
    def start_update(self):
        selected_banks = list(self.selected_rpi_banks)
        if not selected_banks:
            messagebox.showwarning("No selection", "Please select at least one bank on the RPi side.")
            return

        common_banks = [bank for bank in selected_banks if bank in self.sp_banks]
        skipped = [bank for bank in selected_banks if bank not in self.sp_banks]
        for bank in skipped:
            self.harvester.log_message(f"Bank {bank} exists only on RPi – skipped.")
        if not common_banks:
            messagebox.showwarning("No common banks", "None of the selected banks exist in Soundplantage.")
            return
        selected_banks = common_banks

        self.harvester.log_message("▶ Update started – backing up selected banks from RPi...")
        self.btn_prepare.config(state="disabled")

        base = self.harvester.entry_base_path.get()
        profile = self.harvester.get_current_profile_name()
        backup_root = os.path.join(base, "_backups", profile, "performance")
        os.makedirs(backup_root, exist_ok=True)

        for bank in selected_banks:
            bank_backup_dir = os.path.join(backup_root, bank)
            if os.path.exists(bank_backup_dir):
                shutil.rmtree(bank_backup_dir)
            os.makedirs(bank_backup_dir, exist_ok=True)

        update_root = os.path.join(base, "Export", "update")
        if os.path.exists(update_root):
            shutil.rmtree(update_root)
        os.makedirs(update_root, exist_ok=True)

        def on_backup_done(success):
            if not success:
                self.harvester.log_message("❌ Backup failed – update aborted.")
                self._update_buttons_state()
                return
            threading.Thread(target=self._perform_comparison,
                             args=(backup_root, selected_banks, base, update_root),
                             daemon=True).start()

        self.harvester.backup_rpi_performances(backup_root, selected_banks=selected_banks,
                                               callback=on_backup_done)

    def _perform_comparison(self, backup_root, selected_banks, base, update_root):
        sp_root = os.path.join(base, "Soundplantage", "performance")
        update_perf = os.path.join(update_root, "performance")
        os.makedirs(update_perf, exist_ok=True)

        delete_notices = []
        self.deletes = []

        for bank in selected_banks:
            sp_bank_dir = os.path.join(sp_root, bank)
            backup_bank_dir = os.path.join(backup_root, bank)
            update_bank_dir = os.path.join(update_perf, bank)

            sp_files = self._list_perf_files(sp_bank_dir)
            rpi_files = self._list_perf_files(backup_bank_dir) if os.path.isdir(backup_bank_dir) else []

            self.harvester.log_message(f"🔍 {bank}: {len(sp_files)} SP files vs {len(rpi_files)} Backup files")

            sp_files.sort(key=lambda x: x[0])
            rpi_files.sort(key=lambda x: x[0])

            updates = []
            deletes = []
            i = j = 0
            shift_detected = False

            while i < len(sp_files) and j < len(rpi_files):
                sp_idx, sp_name = sp_files[i]
                rpi_idx, rpi_name = rpi_files[j]

                if shift_detected:
                    updates.append(sp_files[i])
                    deletes.append(rpi_files[j])
                    i += 1
                    j += 1
                else:
                    if sp_idx == rpi_idx:
                        if sp_name == rpi_name:
                            sp_path = os.path.join(sp_bank_dir, sp_name)
                            rpi_path = os.path.join(backup_bank_dir, rpi_name)
                            if not self._files_equal(sp_path, rpi_path):
                                updates.append(sp_files[i])
                        else:
                            shift_detected = True
                            updates.append(sp_files[i])
                            deletes.append(rpi_files[j])
                        i += 1
                        j += 1
                    elif sp_idx < rpi_idx:
                        shift_detected = True
                        updates.append(sp_files[i])
                        i += 1
                    else:
                        shift_detected = True
                        deletes.append(rpi_files[j])
                        j += 1

            if i < len(sp_files):
                updates.extend(sp_files[i:])
            if j < len(rpi_files):
                deletes.extend(rpi_files[j:])

            if updates:
                os.makedirs(update_bank_dir, exist_ok=True)
                for idx, fname in updates:
                    src = os.path.join(sp_bank_dir, fname)
                    dst = os.path.join(update_bank_dir, fname)
                    shutil.copy2(src, dst)
                self.harvester.log_message(f"📤 {bank}: {len(updates)} files prepared for update.")
            else:
                self.harvester.log_message(f"✅ {bank}: already up‑to‑date.")

            if deletes:
                for idx, fname in deletes:
                    delete_notices.append(f"🗑️ {bank}/{fname}")
                    self.deletes.append((bank, fname))
                self.harvester.log_message(f"⚠️ {bank}: {len(deletes)} files marked for deletion on RPi.")

        if delete_notices:
            self.harvester.log_message("── Files to delete on RPi ──")
            for msg in delete_notices:
                self.harvester.log_message(msg)

        pdf_src = os.path.join(os.path.dirname(sp_root), PDF_FILENAME)
        if os.path.exists(pdf_src):
            pdf_dst = os.path.join(update_root, PDF_FILENAME)
            shutil.copy2(pdf_src, pdf_dst)
            self.harvester.log_message("📄 Performance List PDF saved to update folder.")

        self.harvester.log_message("✅ Update preparation complete. Ready to transfer to RPi.")
        self.after(0, lambda: self._on_preparation_done(update_root))

    def _on_preparation_done(self, update_root):
        self.update_prepared = True
        self._update_buttons_state()

    # -------------------------------------------------------------------------
    # Upload auf RPi
    # -------------------------------------------------------------------------
    def apply_update_to_rpi(self):
        if not self.update_prepared:
            messagebox.showwarning("Not prepared", "Please run 'Prepare Update' first.")
            return

        base = self.harvester.entry_base_path.get()
        profile = self.harvester.get_current_profile_name()
        backup_root = os.path.join(base, "_backups", profile, "performance")
        deleted_root = os.path.join(base, "_backups", "deleted")
        update_root = os.path.join(base, "Export", "update")
        update_perf = os.path.join(update_root, "performance")
        if not os.path.isdir(update_perf):
            messagebox.showwarning("No update data", "No prepared update data found.")
            return

        self.btn_apply.config(state="disabled")
        self.harvester.log_message("▶ Applying updates to RPi...")

        def task():
            try:
                if self.deletes:
                    for bank, fname in self.deletes:
                        src_backup = os.path.join(backup_root, bank, fname)
                        dst_deleted = os.path.join(deleted_root, bank, fname)
                        if os.path.exists(src_backup):
                            os.makedirs(os.path.dirname(dst_deleted), exist_ok=True)
                            shutil.move(src_backup, dst_deleted)
                            self.harvester.log_message(f"📦 Moved {bank}/{fname} to _backups/deleted/")
                        def ftp_delete(ftp):
                            ftp.cwd(f"/SD/performance/{bank}")
                            ftp.delete(fname)
                            self.harvester.log_message(f"🗑️ Deleted {bank}/{fname} on RPi")
                        safe_ftp_operation(self.creds, ftp_delete, self.harvester.log_message)

                def ftp_upload(ftp):
                    ftp.cwd("/SD/performance")
                    for bank in os.listdir(update_perf):
                        bank_dir = os.path.join(update_perf, bank)
                        if not os.path.isdir(bank_dir):
                            continue
                        try:
                            ftp.cwd(bank)
                        except:
                            ftp.mkd(bank)
                            ftp.cwd(bank)
                        for fname in os.listdir(bank_dir):
                            if fname.lower().endswith('.ini'):
                                local_path = os.path.join(bank_dir, fname)
                                with open(local_path, 'rb') as f:
                                    ftp.storbinary(f"STOR {fname}", f)
                                self.harvester.log_message(f"⬆️ {bank}/{fname} updated.")
                        ftp.cwd("..")

                    pdf_path = os.path.join(update_root, PDF_FILENAME)
                    if os.path.exists(pdf_path):
                        ftp.cwd("/SD")
                        with open(pdf_path, 'rb') as f:
                            ftp.storbinary(f"STOR {PDF_FILENAME}", f)
                        self.harvester.log_message("📄 Performance List PDF uploaded to /SD/")

                safe_ftp_operation(self.creds, ftp_upload, self.harvester.log_message)

                self.harvester.log_message("✅ Updates successfully transferred to RPi.")
                self.after(0, lambda: self._on_apply_done())
            except Exception as e:
                self.harvester.log_message(f"❌ Update transfer failed: {e}")
                self.after(0, lambda: self._update_buttons_state())

        threading.Thread(target=task, daemon=True).start()

    def _on_apply_done(self):
        self.update_prepared = False
        self._update_buttons_state()
        self.harvester.log_message("Update complete. You may close the dialog.")

    # -------------------------------------------------------------------------
    # Hilfsmethoden
    # -------------------------------------------------------------------------
    def _list_perf_files(self, directory):
        if not os.path.isdir(directory):
            return []
        files = os.listdir(directory)
        result = []
        for f in files:
            if f.lower().endswith('.ini'):
                match = re.match(r'^(\d+)', f)
                if match:
                    idx = int(match.group(1))
                    result.append((idx, f))
        return result

    def _files_equal(self, path1, path2):
        try:
            with open(path1, 'r', encoding='utf-8') as f1, \
                 open(path2, 'r', encoding='utf-8') as f2:
                for line1, line2 in zip(f1, f2):
                    if line1.rstrip('\n\r ') != line2.rstrip('\n\r '):
                        return False
                try:
                    next(f1)
                    return False
                except StopIteration:
                    pass
                try:
                    next(f2)
                    return False
                except StopIteration:
                    pass
            return True
        except Exception:
            return False

    def show_summary(self, summary):
        win = tk.Toplevel(self)
        win.title("Update Summary")
        win.configure(bg=COLOR_BG)
        win.geometry("500x300")
        tk.Label(win, text=summary, font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG, wraplength=480).pack(pady=10)

        def open_update_folder():
            update_dir = os.path.join(self.harvester.entry_base_path.get(), "Export", "update")
            if os.path.exists(update_dir):
                os.startfile(update_dir)

        tk.Button(win, text="Open Update Folder", command=open_update_folder,
                  font=FONT_NORMAL, bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                  activebackground=COLOR_BG_SELECT).pack(pady=5)
        tk.Button(win, text="Close", command=win.destroy, font=FONT_NORMAL,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT).pack(pady=5)
        self.destroy()