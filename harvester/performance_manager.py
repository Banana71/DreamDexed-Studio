# performance_manager.py
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import ftplib
import threading
import io
import re
import os
import shutil
import time
import random
from harvester.constants import *
from harvester.widgets import ToolTip
from harvester.ftp_utils import safe_ftp_operation
from .perf2sheet import parse_voice_155, generate_datasheet, sanitize_filename
from harvester.ini_utils import hex_to_text, text_to_hex, parse_ini_for_voices, rebuild_ini_line
from harvester.rename_dialog import RenameDialog
from harvester.midi_utils import send_bank_and_program
from harvester.minidexed_ini import parse_minidexed_ini

class PerformanceManagerFrame(tk.Frame):
    def __init__(self, master, harvester):
        super().__init__(master, bg=COLOR_BG)
        self.harvester = harvester
        self.creds = None
        self.left_path = "/SD"
        self.right_path = "/SD/performance"

        self.source_mode = tk.StringVar(value="rpi")
        base = self.harvester.entry_base_path.get()
        self.pc_base_path = base
        self.pc_current_path = os.path.join(base, "performance")

        self._initial_load = True
        self._loading_right = False
        self._compacting = False
        self._last_pc_time = 0
        self.setup_gui()
        self.bind("<F4>", self.cmd_create_bank_f4)

    # -------------------------------------------------------------------------
    # Verbindungsaufbau (automatisch)
    # -------------------------------------------------------------------------
    def connect_and_refresh(self):
        """Versucht eine FTP-Verbindung mit dem aktuellen Profil herzustellen
        und lädt bei Erfolg die Verzeichnisse. Andernfalls wird ein Hinweis angezeigt."""
        creds = self.harvester.get_active_ftp_creds()
        if not creds:
            self._show_no_connection("No profile selected")
            return
        self.creds = creds
        self._show_connecting()
        threading.Thread(target=self._try_connect, daemon=True).start()

    def _try_connect(self):
        if not self.creds:
            self.after(0, lambda: self._show_no_connection("No connection data"))
            return
        try:
            ftp = ftplib.FTP(self.creds['ip'], timeout=5)
            ftp.login(self.creds['user'], self.creds['password'])
            ftp.cwd("/")
            try:
                ftp.cwd("SD")
            except:
                pass
            self._read_minidexed_ini(ftp)
            ftp.close()
            self.after(0, self._on_connect_success)
        except Exception as e:
            self.after(0, lambda msg=str(e): self._show_no_connection(msg))

    def _read_minidexed_ini(self, ftp):
        """
        Liest /SD/minidexed.ini aus der bereits offenen FTP‑Session
        und übergibt die geparsten Daten an den Harvester.
        """
        try:
            lines = []
            ftp.retrlines('RETR minidexed.ini', lines.append)
            full_text = "\n".join(lines)
            config = parse_minidexed_ini(full_text)
            self.harvester.after(0, self.harvester.on_minidexed_ini_loaded, config)
        except Exception:
            # Lesefehler → Fallback auf Cache
            self.harvester.after(0, self.harvester.on_minidexed_ini_loaded, None)

    def _refresh_both(self):
        """Refreshes both sides without showing a connection message."""
        if self.creds:
            self.load_left()
        else:
            self._show_no_connection("Not connected")

    def _on_connect_success(self):
        self._initial_load = True
        self.load_left()

    def _show_connecting(self):
        self.lbl_right.config(text="Destination: Connecting...")
        self.list_left.delete(0, tk.END)
        self.list_left.insert(tk.END, "⏳ Connecting...")
        for item in self.tree_right.get_children():
            self.tree_right.delete(item)

    def _show_no_connection(self, reason="Not connected"):
        self.lbl_right.config(text="Not connected")
        self.list_left.delete(0, tk.END)
        self.list_left.insert(tk.END, f"❌ {reason}")
        for item in self.tree_right.get_children():
            self.tree_right.delete(item)
        self.harvester.log_message(f"⚠️ Explorer: {reason}")

    # -------------------------------------------------------------------------
    # Log-Hilfen
    # -------------------------------------------------------------------------
    def log(self, msg):
        self.harvester.log_message(msg)

    def log_progress(self, msg):
        self.harvester.log_progress(msg)

    def clear_progress(self):
        self.harvester.clear_progress()

    # -------------------------------------------------------------------------
    # GUI aufbauen
    # -------------------------------------------------------------------------
    def setup_gui(self):
        style = ttk.Style()
        rowheight = int(18 * SCALE_FACTOR)
        style.configure("Treeview",
                        background=COLOR_BG,
                        fieldbackground=COLOR_BG,
                        foreground=COLOR_FG,
                        font=FONT_NORMAL,
                        rowheight=rowheight)
        style.map("Treeview", background=[("selected", COLOR_BG_SELECT)])

        source_frame = tk.Frame(self, bg=COLOR_BG)
        source_frame.pack(fill="x", padx=10, pady=(10, 0))
        tk.Label(source_frame, text="Left source:", font=FONT_BOLD,
                 bg=COLOR_BG, fg=COLOR_FG).pack(side="left", padx=(0, 10))
        self.rb_rpi = tk.Radiobutton(source_frame, text="RPi (FTP)",
                                     variable=self.source_mode, value="rpi",
                                     bg=COLOR_BG, fg=COLOR_FG,
                                     selectcolor="grey",
                                     activebackground=COLOR_BG,
                                     font=FONT_NORMAL,
                                     command=self.on_source_mode_changed)
        self.rb_rpi.pack(side="left", padx=5)
        self.rb_pc = tk.Radiobutton(source_frame, text="PC (local)",
                                    variable=self.source_mode, value="pc",
                                    bg=COLOR_BG, fg=COLOR_FG,
                                    selectcolor="grey",
                                    activebackground=COLOR_BG,
                                    font=FONT_NORMAL,
                                    command=self.on_source_mode_changed)
        self.rb_pc.pack(side="left", padx=5)

        paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=COLOR_BG)
        paned.pack(fill="both", expand=True, padx=10, pady=5)

        left_frame = tk.Frame(paned, bg=COLOR_BG)
        self.lbl_left = tk.Label(left_frame, text="Source: /SD", font=FONT_BOLD,
                                 bg=COLOR_BG, fg=COLOR_FG, anchor="w")
        self.lbl_left.pack(fill="x", pady=5)
        self.list_left = tk.Listbox(left_frame, font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG,
                                    selectbackground=COLOR_BG_SELECT, selectforeground="white",
                                    activestyle="none", highlightthickness=2,
                                    highlightbackground="gray", highlightcolor=COLOR_FG,
                                    selectmode=tk.EXTENDED)
        self.list_left.pack(side="left", fill="both", expand=True)
        scroll_left = tk.Scrollbar(left_frame, orient="vertical", command=self.list_left.yview, bg=COLOR_BG)
        scroll_left.pack(side="right", fill="y")
        self.list_left.config(yscrollcommand=scroll_left.set)
        self.list_left.bind("<Double-Button-1>", self.on_left_double_click)
        self.list_left.bind("<F3>", self.cmd_copy_f3)
        self.list_left.bind("<FocusIn>", lambda e: self.list_left.config(highlightbackground=COLOR_FG))
        self.list_left.bind("<FocusOut>", lambda e: self.list_left.config(highlightbackground="gray"))
        self.list_left.bind("<Delete>", self.cmd_delete_left)
        self.list_left.bind("<ButtonPress-1>", self.on_left_drag_start)
        self.list_left.bind("<B1-Motion>", self.on_left_drag_motion)
        self.list_left.bind("<ButtonRelease-1>", self.on_left_drag_stop)
        paned.add(left_frame, minsize=300)

        right_frame = tk.Frame(paned, bg=COLOR_BG)
        self.lbl_right = tk.Label(right_frame, text="Destination: /performance",
                                  font=FONT_BOLD, bg=COLOR_BG, fg=COLOR_FG, anchor="w")
        self.lbl_right.pack(fill="x", pady=5)
        tree_container = tk.Frame(right_frame, bg=COLOR_BG)
        tree_container.pack(side="left", fill="both", expand=True)
        self.tree_right = ttk.Treeview(tree_container, columns=("Name",), show="tree", takefocus=1)
        self.tree_right.column("#0", width=0, stretch=tk.NO)
        self.tree_right.pack(fill="both", expand=True)
        scroll_right = tk.Scrollbar(right_frame, orient="vertical", command=self.tree_right.yview, bg=COLOR_BG)
        scroll_right.pack(side="right", fill="y")
        self.tree_right.config(yscrollcommand=scroll_right.set)
        self.tree_right.bind("<F2>", self.cmd_edit_f2)
        self.tree_right.bind("<Double-1>", self.on_right_double_click)
        self.tree_right.bind("<Double-Button-3>", self.on_right_double_click_program_change)  # NEU
        self.tree_right.bind("<ButtonPress-1>", self.on_drag_start)
        self.tree_right.bind("<ButtonRelease-1>", self.on_drag_stop)
        self.tree_right.bind("<B1-Motion>", self.on_drag_motion)
        self.tree_right.tag_configure("target", background=COLOR_FG)
        self.tree_right.bind("<F4>", self.cmd_create_bank_f4)
        self.tree_right.bind("<F5>", lambda e: self.compact_performances())
        self.tree_right.bind("<Delete>", self.cmd_delete_right)
        self.tree_right.bind("<Escape>", lambda e: self.tree_right.selection_remove(self.tree_right.selection())) 
        self.tree_right_container = tree_container
        paned.add(right_frame, minsize=300)

        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.pack(fill="x", padx=10, pady=10)
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=0)

        info_frame = tk.Frame(btn_frame, bg=COLOR_BG)
        info_frame.grid(row=0, column=0, sticky="w")
        tk.Label(info_frame, text="Left: Del delete | F3 copy → | Drag & Drop",
                bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).pack(anchor="w")
        tk.Label(info_frame, text="Right: Del delete | F2 edit | F4 banks | F5 reindex | R‑DblClick = Prg Chg",
                bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).pack(anchor="w")

        button_container = tk.Frame(btn_frame, bg=COLOR_BG)
        button_container.grid(row=0, column=1, sticky="e", padx=(20, 0))
        tk.Button(button_container, text="🔄 Reconnect", width=12, font=FONT_NORMAL,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                  command=self.connect_and_refresh).pack(side="left")

    def on_source_mode_changed(self):
        if self.source_mode.get() == "rpi":
            self.load_left()
        else:
            self.pc_current_path = os.path.join(self.pc_base_path, "performance")
            self.load_left()

    def load_left(self):
        if self.source_mode.get() == "rpi":
            self._load_left_ftp()
        else:
            self._load_left_pc()

    def _load_left_ftp(self):
        self.list_left.delete(0, tk.END)
        self.list_left.insert(tk.END, "⏳ Loading...")
        self.lbl_left.config(text=f"Source: {self.left_path}")
        self.fetch_ftp_list(self.left_path, self.update_left_list)

    def _load_left_pc(self):
        self.list_left.delete(0, tk.END)
        path = self.pc_current_path
        if not os.path.isdir(path):
            self.list_left.insert(tk.END, "❌ Folder not found")
            self.lbl_left.config(text="PC: (invalid)")
            return
        try:
            items = os.listdir(path)
        except PermissionError:
            self.list_left.insert(tk.END, "❌ Permission denied")
            self.lbl_left.config(text="PC: (denied)")
            return

        dirs = []
        files = []
        for item in items:
            full = os.path.join(path, item)
            if os.path.isdir(full):
                dirs.append(item)
            else:
                files.append(item)
        dirs.sort(key=str.lower)
        files.sort(key=str.lower)

        if path != self.pc_base_path:
            self.list_left.insert(tk.END, "📁 ..")
        for d in dirs:
            self.list_left.insert(tk.END, f"📁 {d}")
        for f in files:
            if f.lower().endswith('.ini'):
                self.list_left.insert(tk.END, f"📄 {f}")
            elif f.lower().endswith('.txt'):
                self.list_left.insert(tk.END, f"📝 {f}")
            else:
                self.list_left.insert(tk.END, f"📎 {f}")

        if path == self.pc_base_path:
            display = ".\\"
        else:
            try:
                rel = os.path.relpath(path, self.pc_base_path)
            except ValueError:
                rel = path
            display = f".\\{rel}"
        self.lbl_left.config(text=f"PC: {display}")

        if self._initial_load:
            self._initial_load = False
            self.load_right()

    def on_left_double_click(self, event):
        sel = self.list_left.curselection()
        if not sel: return
        item = self.list_left.get(sel[0])
        if self.source_mode.get() == "rpi":
            self._on_left_double_click_ftp(item)
        else:
            self._on_left_double_click_pc(item)

    def _on_left_double_click_ftp(self, item):
        if item.startswith("📁 .."):
            parts = [p for p in self.left_path.split("/") if p]
            if parts: parts.pop()
            self.left_path = "/" + "/".join(parts)
            if self.left_path == "": self.left_path = "/"
            self.load_left()
        elif item.startswith("📁 "):
            folder_name = item.split(" ", 1)[1]
            if self.left_path == "/":
                self.left_path = f"/{folder_name}"
            else:
                self.left_path = f"{self.left_path}/{folder_name}"
            self.load_left()
        elif item.startswith("📄 "):
            filename = item.split(" ", 1)[1]
            if filename.lower().endswith(".pdf"):
                self.open_remote_pdf(self.left_path, filename)

    def _on_left_double_click_pc(self, item):
        if item == "📁 ..":
            parent = os.path.dirname(self.pc_current_path)
            if not parent.startswith(self.pc_base_path):
                return
            self.pc_current_path = parent
            self.load_left()
        elif item.startswith("📁 "):
            folder = item.split(" ", 1)[1]
            new_path = os.path.join(self.pc_current_path, folder)
            if os.path.isdir(new_path):
                self.pc_current_path = new_path
                self.load_left()
        elif item.startswith("📄 ") or item.startswith("📝 ") or item.startswith("📎 "):
            filename = item.split(" ", 1)[1]
            full_path = os.path.join(self.pc_current_path, filename)
            if filename.lower().endswith(".pdf"):
                self.open_local_pdf(full_path)
            elif filename.lower().endswith(".txt"):
                self.open_local_text_file(full_path)

    def open_remote_pdf(self, remote_dir, filename):
        import tempfile, platform, subprocess
        tmp_path = None
        def task():
            nonlocal tmp_path
            try:
                self.harvester.log_message(f"📄 Downloading {filename} ...")
                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", prefix="minidexed_")
                os.close(tmp_fd)
                def ftp_op(ftp):
                    ftp.cwd(remote_dir)
                    with open(tmp_path, 'wb') as f:
                        ftp.retrbinary(f"RETR {filename}", f.write)
                    return None
                safe_ftp_operation(self.creds, ftp_op, self.harvester.log_message)
                self.harvester.log_message(f"✅ Opening {filename}...")
                system = platform.system()
                if system == "Windows":
                    os.startfile(tmp_path)
                elif system == "Darwin":
                    subprocess.Popen(["open", tmp_path])
                else:
                    subprocess.Popen(["xdg-open", tmp_path])
            except Exception as e:
                self.harvester.log_message(f"❌ Could not open PDF: {e}")
        threading.Thread(target=task, daemon=True).start()

    def open_local_pdf(self, filepath):
        import platform, subprocess
        try:
            if platform.system() == "Windows":
                os.startfile(filepath)
            elif platform.system() == "Darwin":
                subprocess.Popen(["open", filepath])
            else:
                subprocess.Popen(["xdg-open", filepath])
            self.log(f"📄 Opened local PDF: {filepath}")
        except Exception as e:
            self.log(f"❌ Could not open PDF: {e}")

    def open_local_text_file(self, filepath):
        """Open a local .txt file in a read-only text viewer window."""
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                content = f.read()
        except Exception as e:
            self.log(f"❌ Could not open text file: {e}")
            return

        win = tk.Toplevel(self)
        win.title(f"Text Viewer - {os.path.basename(filepath)}")
        win.geometry("600x800")
        win.configure(bg=COLOR_BG)

        text_widget = scrolledtext.ScrolledText(
            win, wrap=tk.WORD, font=("Courier New", 10),
            bg=COLOR_BG, fg=COLOR_FG, insertbackground=COLOR_FG
        )
        text_widget.pack(fill="both", expand=True, padx=10, pady=10)
        text_widget.insert(tk.END, content)
        text_widget.config(state=tk.DISABLED)

        btn_close = tk.Button(
            win, text="Close", command=win.destroy,
            bg=COLOR_BG_BUTTON, fg=COLOR_FG,
            activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
            font=FONT_NORMAL, relief="raised", cursor="hand2"
        )
        btn_close.pack(pady=10)

    # --- F3 ---
    def cmd_copy_f3(self, event=None):
        sel = self.list_left.curselection()
        if not sel: return
        item = self.list_left.get(sel[0])
        mode = self.source_mode.get()
        if mode == "rpi":
            self._f3_copy_rpi(item)
        else:
            self._f3_copy_pc(item)

    def _f3_copy_rpi(self, item):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        if item.startswith("📄 "):
            filename = item.split(" ", 1)[1]
            if not filename.lower().endswith(".ini"):
                messagebox.showwarning("Wrong file type", "Please select an .ini file to copy.")
                return
            max_idx = 0
            for child in self.tree_right.get_children():
                val = self.tree_right.item(child, "values")[0]
                if val.startswith("📄 "):
                    fname = val.split(" ", 1)[1]
                    match = re.match(r"^(\d+)_", fname)
                    if match:
                        max_idx = max(max_idx, int(match.group(1)))
            new_idx = max_idx + 1
            if new_idx > 127:
                messagebox.showerror("Limit reached", "Maximum index of 127 has been reached.")
                return
            clean_name = re.sub(r"^\d+_", "", filename)
            new_filename = f"{new_idx:06d}_{clean_name}"
            self.transfer_file(self.left_path, filename, self.right_path, new_filename)
        elif item.startswith("📁 ") and item != "📁 ..":
            bank_name = item.split(" ", 1)[1]
            src_bank_path = f"{self.left_path}/{bank_name}"
            self.copy_bank_rpi_to_rpi(src_bank_path, bank_name)
        else:
            messagebox.showwarning("Invalid selection", "Select a .ini file or a folder (bank) to copy.")

    def _f3_copy_pc(self, item):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        if item.startswith("📄 "):
            filename = item.split(" ", 1)[1]
            if not filename.lower().endswith(".ini"):
                messagebox.showwarning("Wrong file type", "Only .ini files can be copied.")
                return
            local_file = os.path.join(self.pc_current_path, filename)
            max_idx = 0
            for child in self.tree_right.get_children():
                val = self.tree_right.item(child, "values")[0]
                if val.startswith("📄 "):
                    fname = val.split(" ", 1)[1]
                    match = re.match(r"^(\d+)_", fname)
                    if match:
                        max_idx = max(max_idx, int(match.group(1)))
            new_idx = max_idx + 1
            if new_idx > 127:
                messagebox.showerror("Limit reached", "Maximum index of 127 has been reached.")
                return
            clean_name = re.sub(r"^\d+_", "", filename)
            new_filename = f"{new_idx:06d}_{clean_name}"
            self.upload_single_file(local_file, self.right_path, new_filename)
        elif item.startswith("📁 ") and item != "📁 ..":
            bank_name = item.split(" ", 1)[1]
            local_bank_path = os.path.join(self.pc_current_path, bank_name)
            if not os.path.isdir(local_bank_path):
                messagebox.showerror("Error", f"Folder '{bank_name}' not found locally.")
                return
            self.upload_bank_from_pc(local_bank_path, bank_name)
        else:
            messagebox.showwarning("Invalid selection", "Select a .ini file or a folder (bank) to copy.")

    def _ask_overwrite(self, bank_name, result_event):
        overwrite = messagebox.askyesno(
            "Bank already exists",
            f"Bank '{bank_name}' already exists on the device.\n"
            "Overwrite all files inside?"
        )
        self._overwrite_answer = overwrite
        result_event.set()

    def copy_bank_rpi_to_rpi(self, src_path, bank_name):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        dest_path = f"{self.right_path}/{bank_name}"

        def ftp_op(ftp):
            try:
                ftp.cwd(dest_path)
                exists = True
            except Exception:
                exists = False
            if exists:
                answer_event = threading.Event()
                self.after(0, self._ask_overwrite, bank_name, answer_event)
                answer_event.wait()
                if not self._overwrite_answer:
                    return "User cancelled – bank not copied."

            ftp.cwd(src_path)
            items = []
            ftp.retrlines('LIST', items.append)
            files = []
            for line in items:
                line = line.strip()
                name = ""
                if line.startswith('-'):
                    parts = line.split(maxsplit=8)
                    if len(parts) == 9: name = parts[8].strip()
                else:
                    parts = line.split(maxsplit=3)
                    if len(parts) == 4 and "<DIR>" not in line: name = parts[3].strip()
                    else: name = line.split()[-1]
                if name and name.lower().endswith('.ini'):
                    files.append(name)

            ftp.cwd("/")
            for part in self.right_path.strip("/").split("/"):
                ftp.cwd(part)
            try:
                ftp.mkd(bank_name)
            except Exception:
                pass
            ftp.cwd(bank_name)

            for fname in files:
                buf = io.BytesIO()
                ftp.cwd(src_path)
                ftp.retrbinary(f"RETR {fname}", buf.write)
                buf.seek(0)
                ftp.cwd("/")
                for part in self.right_path.strip("/").split("/"):
                    ftp.cwd(part)
                ftp.cwd(bank_name)
                ftp.storbinary(f"STOR {fname}", buf)
                self.log_progress(f"  📄 {fname} copied.")
            self.clear_progress()
            return f"Bank '{bank_name}' copied successfully."

        def task():
            try:
                self.log(f"📁 Copying bank '{bank_name}'...")
                safe_ftp_operation(self.creds, ftp_op, self.log)
                self.log(f"✅ Bank '{bank_name}' copied to {self.right_path}")
                self.after(0, self.connect_and_refresh)
            except Exception as e:
                self.log(f"❌ Error copying bank: {e}")
            finally:
                self.harvester.ftp_busy = False

        self.lbl_right.config(text=f"Destination: {self.right_path} (Copying bank...)")
        threading.Thread(target=task, daemon=True).start()

    def upload_bank_from_pc(self, local_bank_path, bank_name):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        dest_path = f"{self.right_path}/{bank_name}"

        def ftp_op(ftp):
            ftp.cwd("/")
            try:
                ftp.cwd(dest_path)
                exists = True
            except Exception:
                exists = False
            if exists:
                answer_event = threading.Event()
                self.after(0, self._ask_overwrite, bank_name, answer_event)
                answer_event.wait()
                if not self._overwrite_answer:
                    return "User cancelled – upload stopped."

            ftp.cwd("/")
            for part in self.right_path.strip("/").split("/"):
                ftp.cwd(part)
            try:
                ftp.mkd(bank_name)
            except Exception:
                pass
            ftp.cwd(bank_name)

            ini_files = [f for f in os.listdir(local_bank_path) if f.lower().endswith('.ini')]
            for ini in ini_files:
                local_file = os.path.join(local_bank_path, ini)
                self.log_progress(f" ⏳ Uploading {bank_name}/{ini} …")
                with open(local_file, 'rb') as f:
                    ftp.storbinary(f"STOR {ini}", f)
            self.clear_progress()
            return f"Bank '{bank_name}' uploaded."

        def task():
            try:
                self.log(f"📁 Uploading bank '{bank_name}'...")
                safe_ftp_operation(self.creds, ftp_op, self.log)
                self.log(f"✅ Bank '{bank_name}' uploaded to {self.right_path}")
                self.after(0, self.connect_and_refresh)
            except Exception as e:
                self.log(f"❌ Error uploading bank: {e}")
            finally:
                self.harvester.ftp_busy = False

        self.lbl_right.config(text=f"Destination: {self.right_path} (Uploading bank...)")
        threading.Thread(target=task, daemon=True).start()

    def upload_single_file(self, local_file_path, dest_dir, dest_filename):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        try:
            with open(local_file_path, 'rb') as f:
                content = f.read()
        except Exception as e:
            self.log(f"❌ Could not read local file: {e}")
            self.harvester.ftp_busy = False
            return

        def task():
            try:
                def ftp_op(ftp):
                    ftp.cwd(dest_dir)
                    buf = io.BytesIO(content)
                    ftp.storbinary(f"STOR {dest_filename}", buf)
                    return None
                safe_ftp_operation(self.creds, ftp_op, self.log)
                self.log(f"⬆️ {os.path.basename(local_file_path)} → {dest_dir}/{dest_filename}")
                self.after(0, self.connect_and_refresh)
            except Exception as e:
                self.log(f"❌ Upload failed: {e}")
            finally:
                self.harvester.ftp_busy = False
        threading.Thread(target=task, daemon=True).start()

    def ask_delete_confirm(self, filename, confirm_callback):
        dlg = tk.Toplevel(self)
        dlg.withdraw()
        dlg.title("Delete")
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        dlg.transient(self)
        tk.Label(dlg, text=f"Do you really want to delete '{filename}'?",
                 bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL, wraplength=330).pack(pady=30)
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(fill="x")
        def on_yes():
            dlg.destroy()
            confirm_callback()
        def on_no():
            dlg.destroy()
        tk.Button(btn_frame, text="Yes, delete", bg=COLOR_BG_BUTTON, fg=COLOR_FG_WARN, font=FONT_NORMAL,
                  command=on_yes, cursor="hand2", activebackground="#442222").pack(side="left", padx=30)
        tk.Button(btn_frame, text="Cancel", bg=COLOR_BG_BUTTON, fg=COLOR_FG, font=FONT_NORMAL,
                  command=on_no, cursor="hand2", activebackground=COLOR_BG_SELECT).pack(side="right", padx=30)
        w, h = 350, 150
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.deiconify()

    def fetch_ftp_list(self, target_path, callback):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP busy – refresh skipped.")
            return
        self.harvester.ftp_busy = True
        def task():
            def ftp_op(ftp):
                ftp.cwd("/")
                target = target_path.strip("/")
                if target:
                    for part in target.split("/"):
                        ftp.cwd(part)
                pwd = ftp.pwd()
                items = []
                def parse_line(line):
                    line = line.strip()
                    name = ""
                    is_dir = False
                    if "<DIR>" in line:
                        name = line.split("<DIR>", 1)[1].strip()
                        is_dir = True
                    elif line.startswith('d'):
                        parts = line.split(maxsplit=8)
                        if len(parts) == 9: name = parts[8].strip()
                        is_dir = True
                    elif line.startswith('-'):
                        parts = line.split(maxsplit=8)
                        if len(parts) == 9: name = parts[8].strip()
                    else:
                        parts = line.split(maxsplit=3)
                        if len(parts) == 4 and "<DIR>" not in line: name = parts[3].strip()
                        else: name = line.split()[-1]
                    if name and name not in [".", ".."]:
                        items.append((name, is_dir))
                ftp.retrlines('LIST', parse_line)
                dirs = sorted([n for n, d in items if d])
                files = sorted([n for n, d in items if not d])
                self.after(0, lambda: callback(pwd, dirs, files))
                return None
            try:
                safe_ftp_operation(self.creds, ftp_op, self.log)
            except Exception as ex:
                self.after(0, lambda msg=str(ex): self.log(f"❌ FTP Error listing {target_path}: {msg}"))
            finally:
                self.harvester.ftp_busy = False
        threading.Thread(target=task, daemon=True).start()

    def update_left_list(self, pwd, dirs, files):
        self.left_path = pwd
        self.lbl_left.config(text=f"Source: {pwd}")
        self.list_left.delete(0, tk.END)
        if len(pwd.strip("/\\")) > 0:
            self.list_left.insert(tk.END, "📁 ..")
        for d in dirs: self.list_left.insert(tk.END, f"📁 {d}")
        for f in files: self.list_left.insert(tk.END, f"📄 {f}")
        if self._initial_load:
            self._initial_load = False
            self.load_right()

    def load_right(self):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, skipping...")
            return
        if self._loading_right:
            self.log("⏳ Loading already in progress, skipping...")
            return
        self._loading_right = True
        for item in self.tree_right.get_children():
            self.tree_right.delete(item)
        self.lbl_right.config(text=f"Destination: {self.right_path} (Loading...)")
        self.fetch_ftp_list(self.right_path, self.update_right_list)

    def update_right_list(self, pwd, dirs, files):
        self.right_path = pwd
        self.lbl_right.config(text=f"Destination: {pwd}")
        for item in self.tree_right.get_children():
            self.tree_right.delete(item)
        if len(pwd.strip("/\\")) > 0:
            self.tree_right.insert("", "end", values=("📁 ..",))
        for d in dirs:
            self.tree_right.insert("", "end", values=(f"📁 {d}",))
        target_item_id = None
        for f in files:
            item_id = self.tree_right.insert("", "end", values=(f"📄 {f}",))
            if getattr(self, 'item_to_focus', None) == f:
                target_item_id = item_id
        if target_item_id:
            self.tree_right.selection_set(target_item_id)
            self.tree_right.see(target_item_id)
            self.item_to_focus = None
        self._loading_right = False

    def on_right_double_click(self, event):
        sel = self.tree_right.selection()
        if not sel: return
        item = sel[0]
        val = self.tree_right.item(item, "values")[0]
        if val.startswith("📁 .."):
            parts = [p for p in self.right_path.split("/") if p]
            if parts: parts.pop()
            self.right_path = "/" + "/".join(parts)
            if self.right_path == "": self.right_path = "/"
            self.load_right()
        elif val.startswith("📁 "):
            folder_name = val.split(" ", 1)[1]
            self.right_path = f"{self.right_path}/{folder_name}".replace("//", "/")
            self.load_right()
        elif val.startswith("📄 ") and val.endswith(".ini"):
            filename = val.split(" ", 1)[1]
            self.open_rename_dialog(filename)

    # ---------- NEU: Program Change per Rechts-Doppelklick ----------
    def on_right_double_click_program_change(self, event):
        import time
        now = time.time()
        if now - self._last_pc_time < 0.5:   # 500 ms Sperre
            return
        self._last_pc_time = now        
        item = self.tree_right.identify_row(event.y)
        if not item:
            return
        val = self.tree_right.item(item, "values")[0]
        if not val.startswith("📄 "):
            return
        filename = val[2:].strip()
        match = re.match(r"^(\d+)_(.*)\.ini$", filename, re.IGNORECASE)
        if not match:
            self.log(f"⚠️ Could not parse index from {filename}")
            return
        program_index = int(match.group(1)) - 1  # 0‑basiert

        # Bank aus aktuellem right_path extrahieren
        bank_path = self.right_path.rstrip("/")
        bank_folder = os.path.basename(bank_path)
        bank_match = re.match(r"^(\d{3})_", bank_folder)
        if not bank_match:
            self.log(f"⚠️ Could not determine bank index from {bank_folder}")
            return
        bank_index = int(bank_match.group(1)) - 1  # 0‑basiert

        if bank_index < 0 or bank_index > 127 or program_index < 0 or program_index > 127:
            self.log(f"⚠️ Invalid bank/program numbers: bank={bank_index+1}, program={program_index+1}")
            return

        # Harvester fragen
        dev = self.harvester.midi_out_device_index
        chan = self.harvester.midi_out_channel
        if dev < 0:
            self.log("🔇 MIDI Out is disabled (Kein MIDI).")
            return

        try:
            h = self.harvester
            if hasattr(h, '_send_controller_bank_select'):
                h._send_controller_bank_select(bank_index)

            if hasattr(h, '_send_controller_program_change'):
                # Verwende den Kanal aus minidexed_config oder Fallback
                chan_pc = h.minidexed_config.get("performance_select_channel", h.midi_out_channel) if h.minidexed_config else h.midi_out_channel
                h._send_controller_program_change(chan_pc, program_index)
            else:
                send_bank_and_program(dev, chan, bank_index, program_index)

            bank_str = f"{bank_index+1:03d}"
            prog_str = f"{program_index+1:03d}"
            perf_name = match.group(2)
            self.log(f'Prg Chg: {bank_str}:{prog_str} "{perf_name}"')
        except Exception as e:
            self.log(f"❌ Failed to send Program Change: {e}")

    def cmd_edit_f2(self, event=None):
        sel = self.tree_right.selection()
        if not sel: return
        item = sel[0]
        val = self.tree_right.item(item, "values")[0]
        if val.startswith("📄 ") and val.endswith(".ini"):
            self.open_rename_dialog(val.split(" ", 1)[1])

    def open_rename_dialog(self, filename):
        remote_dir = self.right_path
        RenameDialog(self, self.creds, remote_dir, filename, self.load_right, self.harvester)

    def transfer_file(self, src_dir, src_file, dest_dir, dest_file):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True

        def task():
            success = False
            try:
                def ftp_op(ftp):
                    ftp.cwd(src_dir)
                    buf = io.BytesIO()
                    ftp.retrbinary(f"RETR {src_file}", buf.write)
                    buf.seek(0)
                    ftp.cwd("/")
                    ftp.cwd(dest_dir)
                    ftp.storbinary(f"STOR {dest_file}", buf)
                    self.log(f"📋 Copied: {src_dir}/{src_file} → {dest_dir}/{dest_file}")
                    self.item_to_focus = dest_file
                    return None

                safe_ftp_operation(self.creds, ftp_op, self.log)
                success = True

            except Exception as e:
                self.after(0, lambda msg=str(e): messagebox.showerror("Copy error", msg))

            finally:
                self.harvester.ftp_busy = False
            if success:
                self.after(0, self.load_right)

        threading.Thread(target=task, daemon=True).start()

    def execute_reorder(self, old_idx, new_idx, old_filename, new_base_name):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        def task():
            try:
                def ftp_op(ftp):
                    ftp.cwd(self.right_path)
                    lines = []
                    ftp.retrlines('LIST', lines.append)
                    existing_files = {}
                    for line in lines:
                        line = line.strip()
                        fname = ""
                        if line.startswith('-'):
                            parts = line.split(maxsplit=8)
                            if len(parts) == 9: fname = parts[8].strip()
                        else:
                            parts = line.split(maxsplit=3)
                            if len(parts) == 4 and "<DIR>" not in line: fname = parts[3].strip()
                            else: fname = line.split()[-1]
                        if fname:
                            match = re.match(r"^(\d+)_(.*)\.ini$", fname, re.IGNORECASE)
                            if match:
                                existing_files[int(match.group(1))] = fname
                    if old_idx not in existing_files:
                        raise Exception(f"Original file at index {old_idx} was not found on server.")
                    temp_suffix = f"{int(time.time())}_{random.randint(1000,9999)}"
                    temp_filename = f"temp_reorder_{temp_suffix}_{old_filename}"
                    ftp.rename(old_filename, temp_filename)
                    if new_idx < old_idx:
                        for i in range(old_idx - 1, new_idx - 1, -1):
                            if i in existing_files:
                                cur_name = existing_files[i]
                                base = re.sub(r"^\d+_", "", cur_name)
                                shifted_name = f"{i+1:06d}_{base}"
                                ftp.rename(cur_name, shifted_name)
                    elif new_idx > old_idx:
                        for i in range(old_idx + 1, new_idx + 1):
                            if i in existing_files:
                                cur_name = existing_files[i]
                                base = re.sub(r"^\d+_", "", cur_name)
                                shifted_name = f"{i-1:06d}_{base}"
                                ftp.rename(cur_name, shifted_name)
                    final_name = f"{new_idx:06d}_{new_base_name}.ini"
                    ftp.rename(temp_filename, final_name)
                    self.log(f"🔄 Index changed: {old_filename} → Index {new_idx}")
                    self.item_to_focus = final_name
                    self.after(0, self.connect_and_refresh)
                    return None
                safe_ftp_operation(self.creds, ftp_op, self.log)
            except Exception as e:
                self.after(0, lambda m=str(e): messagebox.showerror("Reorder error", m))
            finally:
                self.harvester.ftp_busy = False
        self.lbl_right.config(text=f"Destination: {self.right_path} (Processing changes...)")
        threading.Thread(target=task, daemon=True).start()

    def on_drag_start(self, event):
        item = self.tree_right.identify_row(event.y)
        self.current_target = None

        # Klick in leeren Bereich → Auswahl aufheben und nichts weiter tun
        if not item:
            self.tree_right.selection_remove(self.tree_right.selection())
            self.dragged_item = None
            return

        val = self.tree_right.item(item, "values")[0]
        if val.startswith("📄 "):
            self.dragged_item = item
        else:
            self.dragged_item = None

    def on_drag_motion(self, event):
        if not getattr(self, 'dragged_item', None): return
        target_item = self.tree_right.identify_row(event.y)
        if getattr(self, 'current_target', None) and self.current_target != target_item:
            self.tree_right.item(self.current_target, tags=())
            self.current_target = None
        if target_item and target_item != self.dragged_item:
            val = self.tree_right.item(target_item, "values")[0]
            if val.startswith("📄 "):
                self.tree_right.item(target_item, tags=("target",))
                self.current_target = target_item

    def on_drag_stop(self, event):
        if not getattr(self, 'dragged_item', None): return
        if getattr(self, 'current_target', None):
            self.tree_right.item(self.current_target, tags=())
        target_item = self.tree_right.identify_row(event.y)
        dragged_item = self.dragged_item
        self.dragged_item = None
        self.current_target = None
        if not target_item or target_item == dragged_item: return
        val_drag = self.tree_right.item(dragged_item, "values")[0].replace("📄 ", "", 1)
        val_target = self.tree_right.item(target_item, "values")[0].replace("📄 ", "", 1)
        match_drag = re.match(r"^(\d+)_(.*)\.ini$", val_drag, re.IGNORECASE)
        match_target = re.match(r"^(\d+)_", val_target, re.IGNORECASE)
        if match_drag and match_target:
            old_idx = int(match_drag.group(1))
            new_idx = int(match_target.group(1))
            old_filename = val_drag
            new_base_name = match_drag.group(2)
            if old_idx != new_idx:
                self.execute_reorder(old_idx, new_idx, old_filename, new_base_name)

    def on_left_drag_start(self, event):
        if event.state & (0x0004 | 0x0001):
            return
        idx = self.list_left.nearest(event.y)
        self.list_left.selection_clear(0, tk.END)
        self.list_left.selection_set(idx)
        item = self.list_left.get(idx)
        if item.startswith("📄 ") and item.endswith(".ini"):
            self.left_dragged_item = item.split(" ", 1)[1]
        else:
            self.left_dragged_item = None
        self.current_target = None

    def on_left_drag_motion(self, event):
        if not getattr(self, 'left_dragged_item', None): return
        x_root, y_root = event.x_root, event.y_root
        rx, ry = self.tree_right.winfo_rootx(), self.tree_right.winfo_rooty()
        rw, rh = self.tree_right.winfo_width(), self.tree_right.winfo_height()
        if rx <= x_root <= rx + rw and ry <= y_root <= ry + rh:
            rel_y = y_root - ry
            target_item = self.tree_right.identify_row(rel_y)
            if getattr(self, 'current_target', None) and self.current_target != target_item:
                self.tree_right.item(self.current_target, tags=())
                self.current_target = None
            if target_item:
                val = self.tree_right.item(target_item, "values")[0]
                if val.startswith("📄 "):
                    self.tree_right.item(target_item, tags=("target",))
                    self.current_target = target_item
        else:
            if getattr(self, 'current_target', None):
                self.tree_right.item(self.current_target, tags=())
                self.current_target = None

    def on_left_drag_stop(self, event):
        if not getattr(self, 'left_dragged_item', None): return
        src_filename = self.left_dragged_item
        self.left_dragged_item = None
        if getattr(self, 'current_target', None):
            self.tree_right.item(self.current_target, tags=())
            target_item = self.current_target
            self.current_target = None
            val_target = self.tree_right.item(target_item, "values")[0].replace("📄 ", "", 1)
            match_target = re.match(r"^(\d+)_", val_target, re.IGNORECASE)
            if match_target:
                target_idx = int(match_target.group(1))
                self.execute_cross_drag_transfer(src_filename, target_idx)

    def execute_cross_drag_transfer(self, src_filename, target_idx):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        def task():
            try:
                def ftp_op(ftp):
                    ftp.cwd(self.right_path)
                    lines = []
                    ftp.retrlines('LIST', lines.append)
                    existing_files = {}
                    for line in lines:
                        line = line.strip()
                        fname = ""
                        if line.startswith('-'):
                            parts = line.split(maxsplit=8)
                            if len(parts) == 9: fname = parts[8].strip()
                        else:
                            parts = line.split(maxsplit=3)
                            if len(parts) == 4 and "<DIR>" not in line: fname = parts[3].strip()
                            else: fname = line.split()[-1]
                        if fname:
                            match = re.match(r"^(\d+)_(.*)\.ini$", fname, re.IGNORECASE)
                            if match:
                                existing_files[int(match.group(1))] = fname
                    max_idx = max(existing_files.keys()) if existing_files else -1
                    if max_idx >= 127:
                        raise Exception("Maximum index reached.")
                    for i in range(max_idx, target_idx - 1, -1):
                        if i in existing_files:
                            cur_name = existing_files[i]
                            base = re.sub(r"^\d+_", "", cur_name)
                            ftp.rename(cur_name, f"{i+1:06d}_{base}")
                    ftp.cwd("/")
                    ftp.cwd(self.left_path)
                    buf = io.BytesIO()
                    ftp.retrbinary(f"RETR {src_filename}", buf.write)
                    buf.seek(0)
                    ftp.cwd("/")
                    ftp.cwd(self.right_path)
                    clean_name = re.sub(r"^\d+_", "", src_filename)
                    final_name = f"{target_idx:06d}_{clean_name}"
                    ftp.storbinary(f"STOR {final_name}", buf)
                    self.log(f"📥 Inserted: {src_filename} at position {target_idx} → {final_name}")
                    self.item_to_focus = final_name
                    self.after(0, self.connect_and_refresh)
                    return None
                safe_ftp_operation(self.creds, ftp_op, self.log)
            except Exception as e:
                self.after(0, lambda m=str(e): messagebox.showerror("Transfer error", m))
            finally:
                self.harvester.ftp_busy = False
        self.lbl_right.config(text=f"Destination: {self.right_path} (Inserting...)")
        threading.Thread(target=task, daemon=True).start()

    def cmd_delete_left(self, event=None):
        """Handle delete key in left listbox: .ini files or backup folders."""
        sel = self.list_left.curselection()
        if not sel:
            return

        items = [self.list_left.get(i) for i in sel]
        files = []
        folders = []
        for item in items:
            if item.startswith("📄 "):
                files.append(item.split(" ", 1)[1])
            elif item.startswith("📁 ") and item != "📁 ..":
                folders.append(item.split(" ", 1)[1])

        # Mixed selection is not allowed – user must choose either files or folders
        if files and folders:
            messagebox.showwarning("Mixed selection",
                                   "Please select either only files or only folders to delete.")
            return

        if files:
            # Delete only .ini files (existing behaviour)
            for fname in files:
                if fname.lower().endswith('.ini'):
                    self.ask_delete_confirm(fname, lambda f=fname: self.execute_delete(self.left_path, f))
                else:
                    messagebox.showwarning("Wrong file type", f"Only .ini files can be deleted: {fname}")
            return

        if folders:
            # Validate that all selected folders are allowed backup folders
            allowed = True
            mode = self.source_mode.get()
            if mode == "rpi":
                # Allow only when in /SD (or root) and folder name starts with performance_bu_
                if self.left_path != "/SD":
                    allowed = False
                else:
                    for fname in folders:
                        if not fname.startswith("performance_bu_"):
                            allowed = False
                            break
            else:  # PC mode
                backups_dir = os.path.join(self.pc_base_path, "_backups")
                # Allow deletion anywhere inside _backups (including subfolders)
                if not (os.path.isdir(backups_dir) and self.pc_current_path.startswith(backups_dir)):
                    allowed = False
                # No further name checks – any folder inside _backups is considered a backup

            if not allowed:
                messagebox.showwarning("Not allowed",
                    "You can only delete backup folders.\n"
                    "On the Pi, select 'performance_bu_*' folders inside /SD.\n"
                    "On your PC, navigate into the '_backups' folder (or its subfolders).")
                return

            # Confirm and delete
            self.confirm_delete_backup_folders(folders, lambda: self.delete_backup_folders_left(folders))
            return

    def confirm_delete_backup_folders(self, folder_names, callback):
        """Show a confirmation dialog for multiple backup folders."""
        dlg = tk.Toplevel(self)
        dlg.withdraw()
        dlg.title("Delete backup folders")
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        dlg.transient(self)

        tk.Label(dlg, text="Do you really want to delete these backup folders?",
                 bg=COLOR_BG, fg=COLOR_FG, font=FONT_BOLD, wraplength=400).pack(pady=(30, 10))

        listbox = tk.Listbox(dlg, font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG,
                             selectbackground=COLOR_BG_SELECT, selectforeground="white",
                             height=min(len(folder_names), 12))
        listbox.pack(padx=20, fill="both", expand=True)
        for name in folder_names:
            listbox.insert(tk.END, name)

        tk.Label(dlg, text="This action cannot be undone!", bg=COLOR_BG, fg=COLOR_FG_WARN,
                 font=FONT_NORMAL).pack(pady=10)

        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(fill="x", pady=(0, 30))
        def on_yes():
            dlg.destroy()
            callback()
        def on_no():
            dlg.destroy()
        tk.Button(btn_frame, text="Yes, delete", bg=COLOR_BG_BUTTON, fg=COLOR_FG_WARN,
                  font=FONT_NORMAL, command=on_yes, cursor="hand2",
                  activebackground="#442222").pack(side="left", padx=30)
        tk.Button(btn_frame, text="Cancel", bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                  font=FONT_NORMAL, command=on_no, cursor="hand2",
                  activebackground=COLOR_BG_SELECT).pack(side="right", padx=30)

        w, h = 500, 250 + min(len(folder_names), 12) * 20
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.deiconify()

    def delete_backup_folders_left(self, folder_names):
        """
        Start deletion of multiple backup folders (local or remote).
        Runs in a background thread if remote, otherwise local deletion
        is done directly with a refresh.
        """
        mode = self.source_mode.get()
        if mode == "rpi":
            if self.harvester.ftp_busy:
                self.log("⏳ FTP is busy, please wait...")
                return
            self.harvester.ftp_busy = True
            threading.Thread(target=self._delete_remote_backup_folders,
                             args=(folder_names,), daemon=True).start()
        else:
            # Local deletion – use the *current* PC path (which may be a subfolder of _backups)
            for name in folder_names:
                full_path = os.path.join(self.pc_current_path, name)
                if os.path.isdir(full_path):
                    try:
                        shutil.rmtree(full_path)
                        self.log(f"🗑️ Deleted local backup: {name}")
                    except Exception as e:
                        self.log(f"❌ Failed to delete {name}: {e}")
            self.load_left()

    def _delete_remote_backup_folders(self, folder_names):
        """Thread target: delete remote backup folders sequentially."""
        try:
            for name in folder_names:
                self.log(f"🗑️ Deleting remote folder: {self.left_path}/{name}")
                self._delete_remote_folder(name)
            self.after(0, self.load_left)
        except Exception as e:
            self.after(0, lambda m=str(e): messagebox.showerror("Error deleting", m))
        finally:
            self.harvester.ftp_busy = False

    def _delete_remote_folder(self, folder_name):
        """
        Deletes a single remote folder (with all its contents) inside self.left_path.
        Must be called with a valid FTP connection and ftp_busy already set.
        """
        def ftp_op(ftp):
            ftp.cwd(self.left_path)
            try:
                ftp.cwd(folder_name)
            except Exception as e:
                raise Exception(f"Could not enter folder '{folder_name}': {e}")

            # Delete all files inside
            while True:
                file_list = []
                ftp.retrlines('NLST', file_list.append)
                files = [f for f in file_list if f not in ('.', '..')]
                if not files:
                    break
                for fname in files:
                    try:
                        ftp.delete(fname)
                        self.log_progress(f"   Deleted file: {folder_name}/{fname}")
                    except Exception as e:
                        self.log(f"   ⚠️ Could not delete file '{fname}': {e}")
            self.clear_progress()
            ftp.cwd("..")
            ftp.rmd(folder_name)
            return f"Folder '{folder_name}' deleted."

        safe_ftp_operation(self.creds, ftp_op, self.log)

    def cmd_delete_right(self, event=None):
        sel = self.tree_right.selection()
        if not sel: return
        val = self.tree_right.item(sel[0], "values")[0]
        if not val.startswith("📄 "): return
        self.execute_delete(self.right_path, val.split(" ", 1)[1])

    def execute_delete(self, target_dir, filename):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        def do_delete():
            def task():
                try:
                    def ftp_op(ftp):
                        ftp.cwd(target_dir)
                        ftp.delete(filename)
                        self.log(f"🗑️ Deleted: {target_dir}/{filename}")
                        self.after(0, self.connect_and_refresh)
                        return None
                    safe_ftp_operation(self.creds, ftp_op, self.log)
                except Exception as e:
                    self.after(0, lambda m=str(e): messagebox.showerror("Error deleting", m))
                finally:
                    self.harvester.ftp_busy = False
            threading.Thread(target=task, daemon=True).start()
        self.ask_delete_confirm(filename, do_delete)

    def confirm_delete_bank(self, idx, name, callback):
        dlg = tk.Toplevel(self)
        dlg.withdraw()
        dlg.title("Delete bank")
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        dlg.transient(self)
        tk.Label(dlg, text=f"Really delete bank '{idx:03d}_{name}'?",
                 bg=COLOR_BG, fg=COLOR_FG, font=FONT_BOLD, wraplength=350).pack(pady=(30,10))
        tk.Label(dlg, text="All included performance files will be permanently deleted!",
                 bg=COLOR_BG, fg=COLOR_FG_WARN, font=FONT_NORMAL, wraplength=350).pack(pady=(0,20))
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(fill="x", pady=(0,30))
        def on_yes():
            dlg.destroy()
            callback()
        def on_no():
            dlg.destroy()
        tk.Button(btn_frame, text="Yes, delete", bg=COLOR_BG_BUTTON, fg=COLOR_FG_WARN, font=FONT_NORMAL,
                  command=on_yes, cursor="hand2", activebackground="#442222").pack(side="left", padx=30)
        tk.Button(btn_frame, text="Cancel", bg=COLOR_BG_BUTTON, fg=COLOR_FG, font=FONT_NORMAL,
                  command=on_no, cursor="hand2", activebackground=COLOR_BG_SELECT).pack(side="right", padx=30)
        w, h = 450, 200
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.deiconify()

    def cmd_create_bank_f4(self, event=None):
        target_path = "/SD/performance"
        selected_folder = None
        current_idx = None
        current_name = None
        sel = self.tree_right.selection()
        if sel:
            val = self.tree_right.item(sel[0], "values")[0]
            if val.startswith("📁"):
                folder_display = val[2:].strip()
            else:
                folder_display = val.strip()
            match = re.match(r'^(\d{3})_(.+)$', folder_display)
            if match:
                current_idx = int(match.group(1))
                current_name = match.group(2)
                selected_folder = folder_display
        if selected_folder is not None:
            self.prompt_bank_action(target_path, current_idx, current_name)
        else:
            self.fetch_existing_banks_and_create(target_path)
        return "break"

    def fetch_existing_banks_and_create(self, target_path):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP busy – cannot create bank now.")
            return
        self.harvester.ftp_busy = True
        def task():
            lines = None
            try:
                def ftp_op(ftp):
                    ftp.cwd("/")
                    if target_path != "/":
                        for part in target_path.strip("/").split("/"):
                            ftp.cwd(part)
                    items = []
                    ftp.retrlines('LIST', items.append)
                    return items
                lines = safe_ftp_operation(self.creds, ftp_op, self.log)
            except Exception as e:
                self.after(0, lambda msg=str(e): messagebox.showerror("Error", f"Could not read bank folders:\n{msg}"))
            finally:
                self.harvester.ftp_busy = False
            self.after(0, lambda: self.on_banks_loaded_for_create(lines, target_path))
        threading.Thread(target=task, daemon=True).start()

    def on_banks_loaded_for_create(self, lines, target_path):
        if lines is None:
            self.log("❌ No folder list received.")
            return
        existing = set()
        for line in lines:
            line = line.strip()
            name = ""
            is_dir = False
            if "<DIR>" in line:
                name = line.split("<DIR>", 1)[1].strip()
                is_dir = True
            elif line.startswith('d'):
                parts = line.split(maxsplit=8)
                if len(parts) == 9:
                    name = parts[8].strip()
                is_dir = True
            elif line.startswith('-'):
                parts = line.split(maxsplit=8)
                if len(parts) == 9:
                    name = parts[8].strip()
            else:
                parts = line.split(maxsplit=3)
                if len(parts) == 4 and "<DIR>" not in line:
                    name = parts[3].strip()
                else:
                    name = line.split()[-1]
            if name and is_dir:
                m = re.match(r'^(\d{3})_', name)
                if m:
                    existing.add(int(m.group(1)))
        free = 1
        while free in existing:
            free += 1
            if free > 128:
                messagebox.showerror("Limit reached", "No free index (max. 128).")
                return
        self.prompt_bank_name(free, target_path)

    def prompt_bank_name(self, index, target_path):
        dlg = tk.Toplevel(self)
        dlg.title("Create new bank")
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        dlg.transient(self)
        tk.Label(dlg, text=f"Bank index: {index:03d}", bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_BOLD).pack(pady=(20,5))
        tk.Label(dlg, text="Bank name (max. 14 chars):", bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_NORMAL).pack(pady=(10,0))
        entry_var = tk.StringVar()
        entry = tk.Entry(dlg, textvariable=entry_var, width=30,
                         bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG,
                         font=FONT_NORMAL, relief="solid", borderwidth=1)
        entry.pack(pady=5)
        entry.focus_set()
        def validate_length(*args):
            text = entry_var.get()
            if len(text) > 14:
                entry_var.set(text[:14])
        entry_var.trace('w', validate_length)
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=20)
        def on_ok():
            name = entry_var.get().strip()
            if not name:
                messagebox.showwarning("Input required", "Please enter a bank name.")
                return
            dlg.destroy()
            self.create_bank_folder(index, name, target_path)
        def on_cancel():
            dlg.destroy()
        tk.Button(btn_frame, text="Create", command=on_ok,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                  font=FONT_NORMAL, cursor="hand2").pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=on_cancel,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                  font=FONT_NORMAL, cursor="hand2").pack(side="left", padx=10)
        w, h = 400, 200
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def create_bank_folder(self, index, name, target_path):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP busy – cannot create bank now.")
            return
        self.harvester.ftp_busy = True
        folder_name = f"{index:03d}_{name}"
        self.log(f"📁 Creating bank folder: {folder_name}")
        def task():
            try:
                def ftp_op(ftp):
                    ftp.cwd("/")
                    if target_path != "/":
                        for part in target_path.strip("/").split("/"):
                            ftp.cwd(part)
                    ftp.mkd(folder_name)
                    return f"Folder {folder_name} created."
                result = safe_ftp_operation(self.creds, ftp_op, self.log)
                self.after(0, lambda: self.on_bank_created(folder_name, result))
            except Exception as e:
                self.after(0, lambda msg=str(e): messagebox.showerror("Error", f"Could not create folder:\n{msg}"))
            finally:
                self.harvester.ftp_busy = False
        threading.Thread(target=task, daemon=True).start()

    def on_bank_created(self, folder_name, message):
        self.log(f"✅ {message}")
        self.connect_and_refresh()

    def prompt_bank_action(self, target_path, idx, name):
        dlg = tk.Toplevel(self)
        dlg.title("Edit bank")
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        dlg.transient(self)
        tk.Label(dlg, text=f"Bank: {idx:03d}_{name}", bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_BOLD).pack(pady=(20, 10))
        tk.Label(dlg, text="Which action do you want to perform?",
                 bg=COLOR_BG, fg=COLOR_FG, font=FONT_NORMAL).pack(pady=(0, 15))
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=10)
        def on_rename():
            dlg.destroy()
            self.prompt_rename_bank(target_path, idx, name)
        def on_delete():
            dlg.destroy()
            self.confirm_delete_bank(idx, name, lambda: self.delete_bank_folder(target_path, idx, name))
        tk.Button(btn_frame, text="✏️ Rename", command=on_rename,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                  font=FONT_NORMAL, cursor="hand2", width=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="🗑️ Delete", command=on_delete,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG_WARN, activebackground="#442222",
                  font=FONT_NORMAL, cursor="hand2", width=15).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                  font=FONT_NORMAL, cursor="hand2", width=15).pack(side="left", padx=10)
        w, h = 500, 180
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def prompt_rename_bank(self, target_path, old_idx, old_name):
        dlg = tk.Toplevel(self)
        dlg.title("Rename bank")
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        dlg.transient(self)
        tk.Label(dlg, text=f"Current: {old_idx:03d}_{old_name}", bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_BOLD).pack(pady=(20,5))
        frm_idx = tk.Frame(dlg, bg=COLOR_BG)
        frm_idx.pack(pady=5, fill="x", padx=20)
        tk.Label(frm_idx, text="New index (1-128):", bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_NORMAL).pack(side="left")
        idx_var = tk.StringVar(value=str(old_idx))
        idx_entry = tk.Entry(frm_idx, textvariable=idx_var, width=6,
                             bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG,
                             font=FONT_NORMAL, relief="solid", borderwidth=1)
        idx_entry.pack(side="left", padx=(5,0))
        frm_name = tk.Frame(dlg, bg=COLOR_BG)
        frm_name.pack(pady=5, fill="x", padx=20)
        tk.Label(frm_name, text="New name (max. 14):", bg=COLOR_BG, fg=COLOR_FG,
                 font=FONT_NORMAL).pack(side="left")
        name_var = tk.StringVar(value=old_name)
        name_entry = tk.Entry(frm_name, textvariable=name_var, width=30,
                              bg=COLOR_BG_ENTRY, fg=COLOR_FG, insertbackground=COLOR_FG,
                              font=FONT_NORMAL, relief="solid", borderwidth=1)
        name_entry.pack(side="left", padx=(5,0))
        def validate_length(*args):
            text = name_var.get()
            if len(text) > 14:
                name_var.set(text[:14])
        name_var.trace('w', validate_length)
        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(pady=20)
        def on_ok():
            try:
                new_idx = int(idx_var.get().strip())
                if not 1 <= new_idx <= 128:
                    raise ValueError
            except ValueError:
                messagebox.showwarning("Invalid index", "Index must be a number between 1 and 128.")
                return
            new_name = name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Input required", "Please enter a name.")
                return
            if new_idx == old_idx and new_name == old_name:
                dlg.destroy()
                return
            dlg.destroy()
            self.execute_rename_bank(target_path, old_idx, old_name, new_idx, new_name)
        tk.Button(btn_frame, text="Rename", command=on_ok,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                  font=FONT_NORMAL, cursor="hand2").pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancel", command=dlg.destroy,
                  bg=COLOR_BG_BUTTON, fg=COLOR_FG, activebackground=COLOR_BG_SELECT,
                  font=FONT_NORMAL, cursor="hand2").pack(side="left", padx=10)
        w, h = 450, 220
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")

    def execute_rename_bank(self, target_path, old_idx, old_name, new_idx, new_name):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        old_folder = f"{old_idx:03d}_{old_name}"
        new_folder = f"{new_idx:03d}_{new_name}"
        self.log(f"✏️ Rename requested: {old_folder} → {new_folder}")
        def task():
            try:
                def ftp_op(ftp):
                    ftp.cwd("/")
                    if target_path != "/":
                        for part in target_path.strip("/").split("/"):
                            ftp.cwd(part)
                    items = []
                    ftp.retrlines('LIST', items.append)
                    existing = {}
                    for line in items:
                        line = line.strip()
                        name = ""
                        is_dir = False
                        if "<DIR>" in line:
                            name = line.split("<DIR>", 1)[1].strip()
                            is_dir = True
                        elif line.startswith('d'):
                            parts = line.split(maxsplit=8)
                            if len(parts) == 9:
                                name = parts[8].strip()
                            is_dir = True
                        elif line.startswith('-'):
                            parts = line.split(maxsplit=8)
                            if len(parts) == 9:
                                name = parts[8].strip()
                        else:
                            parts = line.split(maxsplit=3)
                            if len(parts) == 4 and "<DIR>" not in line:
                                name = parts[3].strip()
                            else:
                                name = line.split()[-1]
                        if name and is_dir:
                            m = re.match(r'^(\d{3})_', name)
                            if m:
                                idx = int(m.group(1))
                                existing[idx] = name
                    if new_idx in existing and existing[new_idx] != old_folder:
                        raise Exception(f"Index {new_idx:03d} is already used by '{existing[new_idx]}'.")
                    ftp.rename(old_folder, new_folder)
                    return f"Bank renamed: {old_folder} → {new_folder}"
                result = safe_ftp_operation(self.creds, ftp_op, self.log)
                self.after(0, lambda: self.on_bank_renamed(result))
            except Exception as e:
                self.after(0, lambda m=str(e): messagebox.showerror("Error", m))
            finally:
                self.harvester.ftp_busy = False
        threading.Thread(target=task, daemon=True).start()

    def on_bank_renamed(self, message):
        self.log(f"✅ {message}")
        self.connect_and_refresh()

    def delete_bank_folder(self, target_path, idx, name):
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        folder_name = f"{idx:03d}_{name}"
        self.log(f"🗑️ Deleting bank folder: {folder_name}")
        def task():
            try:
                def ftp_op(ftp):
                    ftp.cwd("/")
                    if target_path != "/":
                        for part in target_path.strip("/").split("/"):
                            ftp.cwd(part)
                    try:
                        ftp.cwd(folder_name)
                    except Exception as e:
                        raise Exception(f"Folder '{folder_name}' not accessible: {e}")
                    while True:
                        file_list = []
                        ftp.retrlines('NLST', file_list.append)
                        files = [f for f in file_list if f and f not in ('.', '..')]
                        if not files:
                            break
                        for fname in files:
                            try:
                                ftp.delete(fname)
                                self.log_progress(f"   🗑️ File deleted: {folder_name}/{fname}")
                            except Exception as e:
                                self.log(f"   ⚠️ Could not delete '{fname}': {e}")
                    self.clear_progress()
                    ftp.cwd("..")
                    ftp.rmd(folder_name)
                    return f"Bank '{folder_name}' deleted."
                result = safe_ftp_operation(self.creds, ftp_op, self.log)
                self.after(0, lambda: self.on_bank_deleted(result))
            except Exception as e:
                self.after(0, lambda m=str(e): messagebox.showerror("Error deleting", m))
            finally:
                self.harvester.ftp_busy = False
        threading.Thread(target=task, daemon=True).start()

    def on_bank_deleted(self, message):
        self.log(f"✅ {message}")
        self.connect_and_refresh()

    def compact_performances(self):
        if self._compacting:
            self.log("⏳ Reindexing already in progress, please wait.")
            return
        if self.harvester.ftp_busy:
            self.log("⏳ FTP is busy, please wait...")
            return
        self.harvester.ftp_busy = True
        self._compacting = True
        target_dir = self.right_path
        self.log(f"🔧 Reindexing performances in {target_dir} ...")
        self.lbl_right.config(text=f"Destination: {target_dir} (Reindexing...)")
        def task():
            try:
                def ftp_op(ftp):
                    ftp.cwd(target_dir)
                    items = []
                    ftp.retrlines('LIST', items.append)
                    entries = []
                    for line in items:
                        line = line.strip()
                        name = ""
                        if line.startswith('-'):
                            parts = line.split(maxsplit=8)
                            if len(parts) == 9:
                                name = parts[8].strip()
                        else:
                            parts = line.split(maxsplit=3)
                            if len(parts) == 4 and "<DIR>" not in line:
                                name = parts[3].strip()
                            else:
                                name = line.split()[-1]
                        if name:
                            m = re.match(r"^(\d+)_(.*)\.ini$", name, re.IGNORECASE)
                            if m:
                                idx = int(m.group(1))
                                rest = m.group(2)
                                entries.append((idx, name, rest))
                    if not entries:
                        self.log("✅ Folder is empty.")
                        return
                    entries.sort(key=lambda x: (x[0], x[1]))
                    new_idx = 1
                    renamed = 0
                    for old_idx, old_name, rest in entries:
                        new_name = f"{new_idx:06d}_{rest}.ini"
                        if new_name != old_name:
                            ftp.rename(old_name, new_name)
                            self.log(f"   ↔️ {old_name} → {new_name}")
                            renamed += 1
                        new_idx += 1
                    if renamed == 0:
                        self.log("✅ Already compact – no changes needed.")
                    else:
                        self.log(f"✅ Reindexing done – {renamed} file(s) renamed.")
                    self.after(0, self.connect_and_refresh)
                    return None
                safe_ftp_operation(self.creds, ftp_op, self.log)
            except Exception as e:
                self.after(0, lambda m=str(e): messagebox.showerror("Error reindexing", m))
            finally:
                self.harvester.ftp_busy = False
                self._compacting = False
        threading.Thread(target=task, daemon=True).start()

    def confirm_delete_backup_folders(self, folder_names, callback):
        """Show a confirmation dialog for multiple backup folders."""
        dlg = tk.Toplevel(self)
        dlg.withdraw()
        dlg.title("Delete backup folders")
        dlg.configure(bg=COLOR_BG)
        dlg.grab_set()
        dlg.transient(self)

        tk.Label(dlg, text="Do you really want to delete these backup folders?",
                 bg=COLOR_BG, fg=COLOR_FG, font=FONT_BOLD, wraplength=400).pack(pady=(30, 10))

        listbox = tk.Listbox(dlg, font=FONT_NORMAL, bg=COLOR_BG, fg=COLOR_FG,
                             selectbackground=COLOR_BG_SELECT, selectforeground="white",
                             height=min(len(folder_names), 12))
        listbox.pack(padx=20, fill="both", expand=True)
        for name in folder_names:
            listbox.insert(tk.END, name)

        tk.Label(dlg, text="This action cannot be undone!", bg=COLOR_BG, fg=COLOR_FG_WARN,
                 font=FONT_NORMAL).pack(pady=10)

        btn_frame = tk.Frame(dlg, bg=COLOR_BG)
        btn_frame.pack(fill="x", pady=(0, 30))
        def on_yes():
            dlg.destroy()
            callback()
        def on_no():
            dlg.destroy()
        tk.Button(btn_frame, text="Yes, delete", bg=COLOR_BG_BUTTON, fg=COLOR_FG_WARN,
                  font=FONT_NORMAL, command=on_yes, cursor="hand2",
                  activebackground="#442222").pack(side="left", padx=30)
        tk.Button(btn_frame, text="Cancel", bg=COLOR_BG_BUTTON, fg=COLOR_FG,
                  font=FONT_NORMAL, command=on_no, cursor="hand2",
                  activebackground=COLOR_BG_SELECT).pack(side="right", padx=30)

        w, h = 500, 250 + min(len(folder_names), 12) * 20
        dlg.update_idletasks()
        x = self.winfo_rootx() + (self.winfo_width() // 2) - (w // 2)
        y = self.winfo_rooty() + (self.winfo_height() // 2) - (h // 2)
        dlg.geometry(f"{w}x{h}+{x}+{y}")
        dlg.deiconify()

    def delete_backup_folders_left(self, folder_names):
        mode = self.source_mode.get()
        if mode == "rpi":
            if self.harvester.ftp_busy:
                self.log("⏳ FTP is busy, please wait...")
                return
            self.harvester.ftp_busy = True
            threading.Thread(target=self._delete_remote_backup_folders,
                            args=(folder_names,), daemon=True).start()
        else:
            for name in folder_names:
                full_path = os.path.join(self.pc_current_path, name)
                if os.path.isdir(full_path):
                    try:
                        shutil.rmtree(full_path)
                        self.log(f"🗑️ Deleted local backup: {name}")
                    except Exception as e:
                        self.log(f"❌ Failed to delete {name}: {e}")
            self.load_left()

    def _delete_remote_backup_folders(self, folder_names):
        """Thread target: delete remote backup folders sequentially."""
        try:
            for name in folder_names:
                self.log(f"🗑️ Deleting remote folder: {self.left_path}/{name}")
                self._delete_remote_folder(name)
            self.after(0, self.load_left)
        except Exception as e:
            self.after(0, lambda m=str(e): messagebox.showerror("Error deleting", m))
        finally:
            self.harvester.ftp_busy = False

    def _delete_remote_folder(self, folder_name):
        """
        Recursively deletes a remote folder (with all files and subfolders)
        inside self.left_path.
        """
        def ftp_op(ftp):
            ftp.cwd(self.left_path)

            def delete_recursive(current_dir):
                """Recursively delete everything inside current_dir, then the directory itself."""
                try:
                    ftp.cwd(current_dir)
                except Exception as e:
                    raise Exception(f"Could not enter '{current_dir}': {e}")

                # Parse LIST output to separate files and subdirectories
                items = []
                ftp.retrlines('LIST', items.append)
                entries = []  # (name, is_dir)

                for line in items:
                    line = line.strip()
                    name = ""
                    is_dir = False
                    if "<DIR>" in line:
                        name = line.split("<DIR>", 1)[1].strip()
                        is_dir = True
                    elif line.startswith('d'):
                        parts = line.split(maxsplit=8)
                        if len(parts) == 9:
                            name = parts[8].strip()
                        is_dir = True
                    elif line.startswith('-'):
                        parts = line.split(maxsplit=8)
                        if len(parts) == 9:
                            name = parts[8].strip()
                    else:
                        parts = line.split(maxsplit=3)
                        if len(parts) == 4 and "<DIR>" not in line:
                            name = parts[3].strip()
                        else:
                            name = line.split()[-1]
                    if name and name not in ('.', '..'):
                        entries.append((name, is_dir))

                # Delete subdirectories first (recursively)
                for name, is_dir in entries:
                    if is_dir:
                        self.log_progress(f"   Deleting folder: {current_dir}/{name}")
                        delete_recursive(name)
                    else:
                        try:
                            ftp.delete(name)
                            self.log_progress(f"   Deleted file: {current_dir}/{name}")
                        except Exception as e:
                            self.log(f"   ⚠️ Could not delete file '{name}': {e}")

                # Go back up and remove the now‑empty directory
                ftp.cwd('..')
                ftp.rmd(current_dir)

            delete_recursive(folder_name)
            self.clear_progress()
            return f"Folder '{folder_name}' deleted."

        safe_ftp_operation(self.creds, ftp_op, self.log)  