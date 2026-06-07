"""
midi_button_config_dialog.py – Table dialog to assign PC keys
to the miniDexed MIDI button functions.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from harvester.constants import (
    COLOR_BG, COLOR_FG, COLOR_FG_DIM, COLOR_BG_SELECT,
    COLOR_BG_BUTTON, COLOR_BG_ENTRY, FONT_NORMAL, FONT_BOLD,
    SCALE_FACTOR, DEFAULT_MIDI_BUTTON_MAP
)


class MidiButtonConfigDialog(tk.Toplevel):
    """
    A modal dialog showing all miniDexed button functions in a table.
    Columns: Function | Default Key | Assigned Key
    - Double-click a row to assign a single key.
    - Press "Assign Key" to run through all functions sequentially.
    """

    def __init__(self, parent, buttons, current_mapping, on_save):
        super().__init__(parent)
        self.title("MIDI Button Configuration")
        self.configure(bg=COLOR_BG)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        self.buttons = buttons                       # from minidexed.ini
        self.mapping = dict(current_mapping)         # {function: keycode}
        self.on_save = on_save

        # Build a lookup: keycode → readable name (filled during captures)
        self.keycode_to_name = {}
        self._capturing = False
        self._capture_func = None
        self._seq_mode = False
        self._seq_items = []
        self._seq_index = 0

        self._build_ui()
        self._populate_table()

        # Window size – height adapts to number of rows
        w = int(600 * SCALE_FACTOR)
        h = int(180 + len(self.buttons) * 28 * SCALE_FACTOR)
        self.geometry(f"{w}x{h}")
        self.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (w // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (h // 2)
        self.geometry(f"+{x}+{y}")

    # ------------------------------------------------------------------
    # UI building
    # ------------------------------------------------------------------
    def _build_ui(self):
        # Instruction label
        lbl = tk.Label(
            self,
            text="Assign PC keys to miniDexed button functions.\n"
                 "Double‑click a row or select it and press [Assign Key] to capture a new key.\n"
                 "Changes are saved when you click [Save].",
            font=FONT_NORMAL,
            fg=COLOR_FG,
            bg=COLOR_BG,
            justify="left"
        )
        lbl.pack(padx=15, pady=(15, 5), anchor="w")

        # Treeview in a frame – height = number of rows, no scrollbar needed
        tree_frame = tk.Frame(self, bg=COLOR_BG)
        tree_frame.pack(fill="both", expand=True, padx=15, pady=5)

        columns = ("function", "default", "assigned")
        self.tree = ttk.Treeview(
            tree_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
            height=len(self.buttons)          # show all rows at once
        )
        self.tree.heading("function", text="Function")
        self.tree.heading("default", text="Default Key")
        self.tree.heading("assigned", text="Assigned Key")

        self.tree.column("function", width=int(120 * SCALE_FACTOR), anchor="w")
        self.tree.column("default", width=int(120 * SCALE_FACTOR), anchor="center")
        self.tree.column("assigned", width=int(120 * SCALE_FACTOR), anchor="center")

        # Style – use a unique name to avoid affecting other Treeviews
        style = ttk.Style()
        style_name = "MidiConfig.Treeview"
        style.configure(style_name,
                        background=COLOR_BG,
                        fieldbackground=COLOR_BG,
                        foreground=COLOR_FG,
                        font=FONT_NORMAL,
                        rowheight=int(24 * SCALE_FACTOR))
        style.map(style_name, background=[("selected", COLOR_BG_SELECT)])

        # Apply the custom style to this Treeview
        self.tree.configure(style=style_name)

        self.tree.pack(fill="both", expand=True)

        self.tree.bind("<Double-1>", self._on_double_click)
        self.tree.bind("<Return>", self._on_double_click)

        # Button bar
        btn_frame = tk.Frame(self, bg=COLOR_BG)
        btn_frame.pack(pady=(5, 15))

        self.btn_assign = tk.Button(
            btn_frame, text="Assign Key", command=self._start_sequence,
            bg=COLOR_BG_BUTTON, fg=COLOR_FG,
            activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
            font=FONT_NORMAL, relief="raised", width=12
        )
        self.btn_assign.pack(side="left", padx=5)

        tk.Button(
            btn_frame, text="Clear", command=self._clear_row,
            bg=COLOR_BG_BUTTON, fg=COLOR_FG,
            activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
            font=FONT_NORMAL, relief="raised", width=8
        ).pack(side="left", padx=5)

        tk.Button(
            btn_frame, text="Save", command=self._save,
            bg=COLOR_BG_BUTTON, fg=COLOR_FG,
            activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
            font=FONT_BOLD, relief="raised", width=10
        ).pack(side="right", padx=5)

        tk.Button(
            btn_frame, text="Cancel", command=self._cancel,
            bg=COLOR_BG_BUTTON, fg=COLOR_FG,
            activebackground=COLOR_BG_SELECT, activeforeground=COLOR_FG,
            font=FONT_NORMAL, relief="raised", width=8
        ).pack(side="right", padx=5)

        # Key capture label (hidden by default)
        self.lbl_capture = tk.Label(
            self, text="", font=FONT_BOLD, fg=COLOR_FG, bg=COLOR_BG, height=2
        )
        self.lbl_capture.pack(pady=(0, 5))

        # Bind for key capture
        self.bind("<KeyPress>", self._on_capture_key)

    # ------------------------------------------------------------------
    # Table population
    # ------------------------------------------------------------------
    def _populate_table(self):
        for btn in self.buttons:
            func = btn["function"]
            default_name = DEFAULT_MIDI_BUTTON_MAP.get(func, "")
            assigned_code = self.mapping.get(func, None)
            assigned_name = self._keycode_to_readable(assigned_code) if assigned_code is not None else ""
            self.tree.insert("", "end", values=(func, default_name, assigned_name))

    # ------------------------------------------------------------------
    # Key name helpers
    # ------------------------------------------------------------------
    def _keycode_to_readable(self, code):
        """Convert a tkinter keycode to a short human-readable string."""
        return self.keycode_to_name.get(code, f"Key {code}")

    # ------------------------------------------------------------------
    # Single capture (double click)
    # ------------------------------------------------------------------
    def _on_double_click(self, event):
        self._start_single_capture()

    def _start_single_capture(self):
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Select a row", "Please select a function row first.")
            return
        item = sel[0]
        func = self.tree.item(item, "values")[0]
        self._capture_func = func
        self._capturing = True
        self.lbl_capture.config(
            text=f"Press the desired key for «{func}» ... (Esc to cancel)"
        )
        self.btn_assign.config(state="disabled")

    # ------------------------------------------------------------------
    # Sequential capture (Assign Key button)
    # ------------------------------------------------------------------
    def _start_sequence(self):
        if self._capturing or self._seq_mode:
            return
        self._seq_items = [btn["function"] for btn in self.buttons]
        self._seq_index = 0
        self._seq_mode = True
        self._update_sequence_label()
        self.btn_assign.config(state="disabled")

    def _update_sequence_label(self):
        if not self._seq_mode:
            return
        func = self._seq_items[self._seq_index]
        note = None
        for btn in self.buttons:
            if btn["function"] == func:
                note = btn["note"]
                break
        note_str = f" (MIDI {note})" if note is not None else ""
        self.lbl_capture.config(
            text=f"Press key for {func}{note_str} – Enter=skip, Esc=cancel"
        )
        # Highlight the current row
        for item in self.tree.get_children():
            if self.tree.item(item, "values")[0] == func:
                self.tree.selection_set(item)
                self.tree.see(item)
                break

    def _advance_sequence(self):
        self._seq_index += 1
        if self._seq_index >= len(self._seq_items):
            self._seq_mode = False
            self.lbl_capture.config(text="All functions assigned.")
            self.btn_assign.config(state="normal")
        else:
            self._update_sequence_label()

    def _cancel_sequence(self):
        self._seq_mode = False
        self.lbl_capture.config(text="Assignment cancelled.")
        self.btn_assign.config(state="normal")

    # ------------------------------------------------------------------
    # Key event handler (dispatches to single or sequential mode)
    # ------------------------------------------------------------------
    def _on_capture_key(self, event):
        # Sequential mode
        if self._seq_mode:
            if event.keysym == "Escape":
                self._cancel_sequence()
                return
            if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R",
                                "Alt_L", "Alt_R", "Win_L", "Win_R", "Caps_Lock"):
                return
            func = self._seq_items[self._seq_index]
            if event.keysym == "Return":
                self._advance_sequence()
                return
            # Assign key
            kc = event.keycode
            self.mapping[func] = kc
            self.keycode_to_name[kc] = event.keysym
            for item in self.tree.get_children():
                if self.tree.item(item, "values")[0] == func:
                    self.tree.item(item, values=(func,
                                                 DEFAULT_MIDI_BUTTON_MAP.get(func, ""),
                                                 self._keycode_to_readable(kc)))
                    break
            self._advance_sequence()
            return

        # Single capture mode
        if self._capturing:
            if event.keysym == "Escape":
                self._cancel_capture()
                return
            if event.keysym in ("Shift_L", "Shift_R", "Control_L", "Control_R",
                                "Alt_L", "Alt_R", "Win_L", "Win_R", "Caps_Lock"):
                return

            kc = event.keycode
            func = self._capture_func
            self.mapping[func] = kc
            self.keycode_to_name[kc] = event.keysym

            for item in self.tree.get_children():
                if self.tree.item(item, "values")[0] == func:
                    self.tree.item(item, values=(func,
                                                 DEFAULT_MIDI_BUTTON_MAP.get(func, ""),
                                                 self._keycode_to_readable(kc)))
                    break
            self._cancel_capture()

    def _cancel_capture(self):
        self._capturing = False
        self._capture_func = None
        self.lbl_capture.config(text="")
        self.btn_assign.config(state="normal")

    # ------------------------------------------------------------------
    # Clear row
    # ------------------------------------------------------------------
    def _clear_row(self):
        sel = self.tree.selection()
        if not sel:
            return
        item = sel[0]
        func = self.tree.item(item, "values")[0]
        if func in self.mapping:
            del self.mapping[func]
        self.tree.item(item, values=(func,
                                     DEFAULT_MIDI_BUTTON_MAP.get(func, ""),
                                     ""))

    # ------------------------------------------------------------------
    # Save / Cancel
    # ------------------------------------------------------------------
    def _save(self):
        self.on_save(self.mapping)
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.grab_release()
        self.destroy()