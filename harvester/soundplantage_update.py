# harvester/soundplantage_update.py
import tkinter as tk
from tkinter import messagebox, scrolledtext
import threading
import requests
import io
import zipfile
import os
import difflib
import json
from datetime import datetime
from harvester.constants import *
from harvester.ftp_utils import safe_ftp_operation

GITHUB_API_TREES = "https://api.github.com/repos/Banana71/Soundplantage/git/trees/main?recursive=1"
ZIP_URL = "https://github.com/Banana71/Soundplantage/archive/refs/heads/main.zip"
PDF_FILENAME = "Performance List.pdf"
REPO_PREFIX = "Soundplantage-main/"
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".soundplantage_cache")

class SoundplantageUpdateDialog(tk.Toplevel):
    def __init__(self, parent, creds, harvester):
        super().__init__(parent)
        self.harvester = harvester
        self.creds = creds
        self.banks = []
        self.selected_banks = set()
        self.pdf_selected = True
        self.downloaded_files = {}
        self.pdf_content = None
        self.user_changed_files = []
        self.backup_timestamps = {}

        self.title("Soundplantage Update")
        self.configure(bg=COLOR_BG)

        scale = self.harvester.scale
        w = int(400 * scale)
        h = int(520 * scale)
        self.geometry(f"{w}x{h}")

        self.update_idletasks()
        pw = parent.winfo_width()
        ph = parent.winfo_height()
        px = parent.winfo_rootx()
        py = parent.winfo_rooty()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        self.grab_set()
        self.build_gui()
        self.load_bank_list()

    def build_gui(self):
        header = tk.Label(self, text="Select banks to update", font=FONT_BOLD,
                          bg=COLOR_BG, fg=COLOR_FG)
        header.pack(pady=10)

        list_frame = tk.Frame(self, bg=COLOR_BG)
        list_frame.pack(fill="both", expand=True, padx=10, pady=5)

        self.listbox = tk.Listbox(list_frame, selectmode=tk.SINGLE, font=FONT_NORMAL,
                                  bg=COLOR_BG, fg=COLOR_FG, relief="flat",
                                  selectbackground=COLOR_BG_SELECT, selectforeground=COLOR_FG,
                                  highlightthickness=1, highlightcolor=COLOR_FG,
                                  highlightbackground=COLOR_FG_DIM)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview, bg=COLOR_BG)
        scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)
        self.listbox.bind("<ButtonRelease-1>", self.toggle_item)

        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.pack(fill="x", padx=10, pady=5)
        btn_style = {"font": FONT_SMALL, "bg": COLOR_BG_BUTTON, "fg": COLOR_FG,
                     "activebackground": COLOR_BG_SELECT, "activeforeground": COLOR_FG,
                     "relief": "raised", "cursor": "hand2"}
        tk.Button(btn_frame, text="[X] All", command=self.select_all, **btn_style).pack(side="left", padx=2)
        tk.Button(btn_frame, text="[ ] None", command=self.select_none, **btn_style).pack(side="left", padx=2)

        action_frame = tk.Frame(self, bg=COLOR_BG)
        action_frame.pack(fill="x", padx=10, pady=10)
        self.download_btn = tk.Button(action_frame, text="Download", command=self.start_download, **btn_style)
        self.download_btn.pack(side="left", padx=5)
        tk.Button(action_frame, text="Cancel", command=self.destroy, **btn_style).pack(side="left", padx=5)

        self.status = tk.Label(self, text="", font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG)
        self.status.pack(pady=5)

    def load_bank_list(self):
        self.status.config(text="Loading bank list from GitHub...")
        threading.Thread(target=self._fetch_banks, daemon=True).start()

    def _fetch_banks(self):
        try:
            resp = requests.get(GITHUB_API_TREES, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            banks_set = set()
            for item in data.get("tree", []):
                if item["type"] == "tree" and item["path"].startswith("performance/") and item["path"].count("/") == 1:
                    bank_name = item["path"].split("/", 1)[1]
                    banks_set.add(bank_name)
            self.banks = sorted(banks_set)
        except Exception as e:
            self.banks = []
            self.after(0, lambda: messagebox.showerror("Error", f"Failed to load banks:\n{e}"))
        self.after(0, self._update_listbox)

    def _update_listbox(self):
        self.listbox.delete(0, tk.END)
        if not self.banks:
            self.status.config(text="No banks found or error occurred.")
            return
        for bank in self.banks:
            prefix = "[X]  " if bank in self.selected_banks else "[ ]  "
            self.listbox.insert(tk.END, prefix + bank)
        pdf_prefix = "[X]  " if self.pdf_selected else "[ ]  "
        self.listbox.insert(tk.END, pdf_prefix + "Performance List PDF")
        self.status.config(text=f"{len(self.banks)} banks loaded. Select and click Download.")

    def toggle_item(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        if idx == len(self.banks):
            self.pdf_selected = not self.pdf_selected
        else:
            bank = self.banks[idx]
            if bank in self.selected_banks:
                self.selected_banks.remove(bank)
            else:
                self.selected_banks.add(bank)
        self._update_listbox()
        self.listbox.selection_set(idx)

    def select_all(self):
        self.selected_banks = set(self.banks)
        self.pdf_selected = True
        self._update_listbox()

    def select_none(self):
        self.selected_banks.clear()
        self.pdf_selected = False
        self._update_listbox()

    def start_download(self):
        if not self.selected_banks and not self.pdf_selected:
            messagebox.showwarning("No selection", "Please select at least one bank or the PDF.")
            return
        self.download_btn.config(state="disabled")
        self.status.config(text="Downloading repository (single ZIP) ...")
        threading.Thread(target=self._download_selected, daemon=True).start()

    def _download_selected(self):
        self.downloaded_files = {}
        self.pdf_content = None

        try:
            resp = requests.get(ZIP_URL, timeout=30)
            resp.raise_for_status()
            zip_data = io.BytesIO(resp.content)
        except Exception as e:
            self.harvester.log_message(f"❌ Failed to download repository ZIP: {e}")
            self.after(0, lambda: self.status.config(text="Download failed."))
            self.after(0, lambda: self.download_btn.config(state="normal"))
            return

        try:
            with zipfile.ZipFile(zip_data) as zf:
                for bank in self.selected_banks:
                    bank_prefix = f"{REPO_PREFIX}performance/{bank}/"
                    bank_files = {}
                    for name in zf.namelist():
                        if name.startswith(bank_prefix) and name.endswith(".ini"):
                            filename = name[len(bank_prefix):]
                            if filename:
                                bank_files[filename] = zf.read(name)
                    if bank_files:
                        self.downloaded_files[bank] = bank_files
                        self.harvester.log_message(f"📥 Extracted {len(bank_files)} files from {bank}")
                    else:
                        self.harvester.log_message(f"⚠️ No .ini files found in {bank}")

                if self.pdf_selected:
                    pdf_path = f"{REPO_PREFIX}{PDF_FILENAME}"
                    try:
                        self.pdf_content = zf.read(pdf_path)
                        self.harvester.log_message("📄 Performance List PDF extracted.")
                    except KeyError:
                        self.harvester.log_message(f"⚠️ PDF '{PDF_FILENAME}' not found in ZIP.")
        except Exception as e:
            self.harvester.log_message(f"❌ Error processing ZIP: {e}")

        self.after(0, self._ask_upload)

    def _ask_upload(self):
        self.download_btn.config(state="normal")
        if not self.downloaded_files and not self.pdf_content:
            self.status.config(text="Download failed or no files found.")
            return
        msg = f"{len(self.downloaded_files)} bank(s) downloaded."
        if self.pdf_content:
            msg += "\nPerformance List PDF ready."
        msg += "\n\nDo you want to write them to the Raspberry Pi?"
        answer = messagebox.askyesno("Write to miniDexed / DreamDexed", msg)
        if answer:
            self.status.config(text="Comparing files...")
            threading.Thread(target=self._compare_and_upload, daemon=True).start()
        else:
            self.status.config(text="Update cancelled.")
            self.destroy()

    def _compare_and_upload(self):
        base = "/SD/performance"
        os.makedirs(CACHE_DIR, exist_ok=True)
        self.user_changed_files = []
        uploaded = 0
        skipped = 0

        for bank, repo_files in self.downloaded_files.items():
            # load cache for this bank
            cache_file = os.path.join(CACHE_DIR, f"{bank}.json")
            cache = {}
            if os.path.exists(cache_file):
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        cache = json.load(f)
                except:
                    cache = {}

            # get current RPi files for this bank
            rpi_files = {}
            def ftp_get_files(ftp):
                ftp.cwd(base)
                try:
                    ftp.cwd(bank)
                except:
                    return  # bank doesn't exist on RPi
                items = []
                ftp.retrlines('LIST', items)
                for line in items:
                    line = line.strip()
                    if "<DIR>" in line or line.startswith('d'):
                        continue
                    parts = line.split()
                    if len(parts) >= 4 and parts[-1].endswith(".ini"):
                        filename = parts[-1]
                        # download content
                        buf = io.BytesIO()
                        ftp.retrbinary(f"RETR {filename}", buf.write)
                        rpi_files[filename] = buf.getvalue()
            try:
                safe_ftp_operation(self.creds, ftp_get_files, self.harvester.log_message)
            except Exception as e:
                self.harvester.log_message(f"⚠️ Could not read bank {bank}: {e}")
                continue

            # prepare new cache
            new_cache = {}   # will store hex digests or file hashes (we use content for simplicity)
            for filename, repo_content in repo_files.items():
                new_cache[filename] = repo_content.hex()  # store hex for future comparison

                rpi_content = rpi_files.get(filename)
                if rpi_content is None:
                    # new file, upload
                    self._upload_file(base, bank, filename, repo_content)
                    uploaded += 1
                elif rpi_content == repo_content:
                    # identical, skip
                    skipped += 1
                else:
                    # different: check cache
                    old_hex = cache.get(filename)
                    if old_hex is not None and rpi_content.hex() == old_hex:
                        # developer change, upload new
                        self._backup_file(base, bank, filename, rpi_content)
                        self._upload_file(base, bank, filename, repo_content)
                        uploaded += 1
                    else:
                        # user change, save to _User_Changes
                        self._save_user_change(base, bank, filename, rpi_content, repo_content)
                        self.user_changed_files.append((bank, filename))
                        skipped += 1

            # handle files only on RPi (user creations) – ignore them, they stay
            # write updated cache
            try:
                with open(cache_file, "w", encoding="utf-8") as f:
                    json.dump(new_cache, f)
            except:
                pass

        # PDF upload separately
        if self.pdf_content:
            try:
                def ftp_put_pdf(ftp):
                    ftp.cwd("/SD")
                    buf = io.BytesIO(self.pdf_content)
                    ftp.storbinary(f"STOR {PDF_FILENAME}", buf)
                    self.harvester.log_message(f"📄 Uploaded {PDF_FILENAME} to /SD/")
                safe_ftp_operation(self.creds, ftp_put_pdf, self.harvester.log_message)
            except Exception as e:
                self.harvester.log_message(f"❌ PDF upload error: {e}")

        summary = f"Update complete: {uploaded} files updated, {skipped} unchanged, {len(self.user_changed_files)} user-modified files saved."
        self.harvester.log_message(summary)
        self.after(0, lambda: self.show_summary(summary))

    def _upload_file(self, base, bank, filename, content):
        def ftp_op(ftp):
            ftp.cwd(base)
            try:
                ftp.cwd(bank)
            except:
                ftp.mkd(bank)
                ftp.cwd(bank)
            buf = io.BytesIO(content)
            ftp.storbinary(f"STOR {filename}", buf)
            self.harvester.log_message(f"⬆️ Updated {bank}/{filename}")
        safe_ftp_operation(self.creds, ftp_op, self.harvester.log_message)

    def _backup_file(self, base, bank, filename, content):
        # create backup in same folder with timestamp
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"{filename}.backup-{ts}"
        def ftp_op(ftp):
            ftp.cwd(f"{base}/{bank}")
            buf = io.BytesIO(content)
            ftp.storbinary(f"STOR {backup_name}", buf)
        try:
            safe_ftp_operation(self.creds, ftp_op, self.harvester.log_message)
        except:
            pass

    def _save_user_change(self, base, bank, filename, content, repo_content):
        # Save original user file in _User_Changes/bank/
        user_bank = "_User_Changes"
        def ftp_op(ftp):
            ftp.cwd(base)
            try:
                ftp.cwd(user_bank)
            except:
                ftp.mkd(user_bank)
                ftp.cwd(user_bank)
            try:
                ftp.cwd(bank)
            except:
                ftp.mkd(bank)
                ftp.cwd(bank)
            buf = io.BytesIO(content)
            ftp.storbinary(f"STOR {filename}", buf)
            self.harvester.log_message(f"📦 User file saved in {user_bank}/{bank}/{filename}")
        safe_ftp_operation(self.creds, ftp_op, self.harvester.log_message)

    def show_summary(self, summary):
        # Show summary in a small window with diff possibility
        win = tk.Toplevel(self)
        win.title("Update Summary")
        win.configure(bg=COLOR_BG)
        win.geometry("500x400")
        tk.Label(win, text=summary, font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG, wraplength=480).pack(pady=10)

        if self.user_changed_files:
            tk.Label(win, text="User-modified files (not overwritten):", font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_FG).pack(anchor="w", padx=10)
            for bank, fname in self.user_changed_files:
                tk.Label(win, text=f"• {bank}/{fname}", font=FONT_SMALL, bg=COLOR_BG, fg=COLOR_FG_WARN).pack(anchor="w", padx=30)

        tk.Button(win, text="Close", command=win.destroy, font=FONT_NORMAL,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT).pack(pady=10)
        self.destroy()
