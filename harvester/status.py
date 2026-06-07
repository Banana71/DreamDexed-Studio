# harvester/status.py
import os
import threading

from harvester.ini_utils import parse_ini_for_voices, hex_to_text
from harvester.ftp_utils import safe_ftp_operation
from harvester.constants import PERF_IMPORT


def run_status_scan(harvester):
    threading.Thread(target=_status_thread, args=(harvester,), daemon=True).start()


def _status_thread(harvester):
    # --- Lokaler INIT‑Scan (unverändert) ---
    base = harvester.entry_base_path.get()
    perf_dir = os.path.join(base, PERF_IMPORT)
    if os.path.isdir(perf_dir):
        harvester.log_message(" - Scanning local performances for INIT voices...")
        init_paths = []
        for root, dirs, files in os.walk(perf_dir):
            for file in files:
                if not file.lower().endswith(".ini"):
                    continue
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, perf_dir)
                if rel_path.startswith(f"128_Laboratory{os.sep}"):
                    continue
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        lines = f.readlines()
                except Exception:
                    continue
                tg_map = parse_ini_for_voices(lines)
                has_init = any(
                    hex_to_text(tg_map[tg].get('hex', '')).upper().startswith("INIT")
                    for tg in range(1, 9) if tg_map[tg].get('hex')
                )
                if has_init:
                    init_paths.append(rel_path)
        if init_paths:
            harvester.log_message(f"INIT voices found in {len(init_paths)} performance(s):")
            for p in init_paths:
                harvester.log_message(f"  - {p}")
        else:
            harvester.log_message("No performances with INIT voice found locally.")
    else:
        harvester.log_message("Local performance folder not found.")

    # --- Remote‑Scan ---
    creds = harvester.get_active_ftp_creds()
    if creds:
        harvester.log_message(f" - Scanning {harvester.get_current_profile_name()} for performance banks...")
        try:
            def ftp_op(ftp):
                # --- Sysex-Dateien zählen ---
                try:
                    ftp.cwd("/SD/sysex/voice")
                    files = []
                    ftp.retrlines('NLST', files.append)
                    syx_count = sum(1 for f in files if f.lower().endswith('.syx'))
                    if syx_count > 0:
                        harvester.log_message(f"Sysex files in /sysex/voice/: {syx_count}")
                    else:
                        harvester.log_message("No .syx files found in /sysex/voice/")
                except Exception:
                    harvester.log_message("No sysex folder found on DreamDexed.")

                # --- Bank-Ordner analysieren (unverändert) ---
                ftp.cwd("/SD/performance")
                items = []
                ftp.retrlines('LIST', items.append)
                bank_folders = []
                for line in items:
                    line = line.strip()
                    name = None
                    if "<DIR>" in line:
                        name = line.split("<DIR>", 1)[1].strip()
                    elif line.startswith('d'):
                        parts = line.split(maxsplit=8)
                        if len(parts) == 9:
                            name = parts[8].strip()
                    if name and name not in ('.', '..'):
                        bank_folders.append(name)

                bank_infos = []
                default_entries = []

                for bank in bank_folders:
                    try:
                        ftp.cwd(bank)
                        files = []
                        ftp.retrlines('NLST', files.append)
                        ini_count = 0
                        default_names = []
                        for fname in files:
                            if fname.lower().endswith('.ini'):
                                ini_count += 1
                                if 'perf000' in fname.lower():
                                    default_names.append(fname)
                        bank_infos.append((bank, ini_count))
                        for df in default_names:
                            default_entries.append((bank, df))
                        ftp.cwd("..")
                    except Exception as e:
                        harvester.log_message(f"  Could not access bank {bank}: {e}")

                if bank_infos:
                    harvester.log_message("\n            - - - Bank Overview - - -")
                    for bank, count in bank_infos:
                        padding = int((20 - len(bank)) * 1.7)
                        spaces = " " * padding
                        harvester.log_message(f"{bank}{spaces}- {count:03d} Performances")

                if default_entries:
                    harvester.log_message("--- Unnamed Performances (Perf000) ---")
                    for bank, fname in default_entries:
                        harvester.log_message(f"  {bank}/{fname}")

                return None

            safe_ftp_operation(creds, ftp_op, harvester.log_message)
        except Exception as e:
            harvester.log_message(f"Error scanning RPi: {e}")
    else:
        harvester.log_message("No FTP profile selected. Skipping RPi scan.")

    harvester.log_message("\n - - - STATUS SCAN COMPLETED - - -")