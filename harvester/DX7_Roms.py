
# harvester/DX7_Roms.py
import os
import shutil
import re

# --- Konfiguration ---
SOURCE_DIR = "DX7 Cartridges"
TARGET_VOICE_DIR = os.path.join("Export", "sysex", "voice")
TARGET_LAB_DIR = os.path.join("Export", "performance", "128_Laboratory")

# ----------------------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------------------
def get_used_indices(directory, exclude_suffixes=None):
    """Sammelt alle belegten Indizes, klammert aber definierte Dateiendungen aus."""
    if exclude_suffixes is None:
        exclude_suffixes = []
    indices = set()
    if not os.path.exists(directory):
        return indices
    for f in os.listdir(directory):
        if any(f.endswith(suffix) for suffix in exclude_suffixes):
            continue
        match = re.match(r'^(\d+)_', f)
        if match:
            indices.add(int(match.group(1)))
    return indices

def get_next_free_index(used_indices, start_at=1):
    """Sucht die kleinste freie Zahl ab start_at."""
    idx = start_at
    while idx in used_indices:
        idx += 1
    used_indices.add(idx)
    return idx

def get_sorted_dx7_files():
    """
    Liefert eine Liste aller .syx-Dateien im Quellordner, sortiert nach:
    1. Dateien, die mit 'rom' beginnen (alphabetisch)
    2. Die vier speziellen dx7iifd*-Dateien in fester Reihenfolge
    3. Alle restlichen .syx (alphabetisch)
    """
    if not os.path.exists(SOURCE_DIR):
        return []
    all_files = [f for f in os.listdir(SOURCE_DIR) if f.lower().endswith('.syx')]
    
    # Gruppe 1: rom*.syx
    rom_files = sorted([f for f in all_files if f.lower().startswith('rom')])
    
    # Gruppe 2: feste Reihenfolge
    ii_sequence = ["dx7iifdvoice32.syx", "dx7iifdvoice64.syx", "dx7iifdvoice32b.syx", "dx7iifdvoice64b.syx"]
    ii_files = [f for f in ii_sequence if f in all_files]
    
    # Gruppe 3: alle anderen .syx
    other_files = sorted([f for f in all_files 
                          if not f.lower().startswith('rom') and f not in ii_sequence])
    
    return rom_files + ii_files + other_files

def clean_old_dx7_voices(target_dir, source_basenames, log_func):
    """
    Löscht im Zielordner alle .syx-Dateien, deren Basisname (ohne Index)
    in source_basenames vorkommt.
    """
    if not os.path.exists(target_dir):
        return
    for f in os.listdir(target_dir):
        if not f.lower().endswith('.syx'):
            continue
        # Entferne führenden Index (z.B. "000042_")
        match = re.match(r'^\d+_(.*)$', f)
        if match:
            base = match.group(1)
            if base in source_basenames:
                try:
                    os.remove(os.path.join(target_dir, f))
                    log_func(f"  Old DX7 voice deleted: {f}")
                except Exception as e:
                    log_func(f"  Warning: Could not delete {f}: {e}")

def clean_old_templates(target_dir, template_basenames, log_func):
    """
    Löscht im Zielordner (128_Laboratory) die beiden Template-Dateien,
    falls sie existieren (basierend auf Basisnamen ohne Index).
    """
    if not os.path.exists(target_dir):
        return
    for f in os.listdir(target_dir):
        if not f.endswith('.ini'):
            continue
        match = re.match(r'^\d+_(.*)$', f)
        if match:
            base = match.group(1)
            if base in template_basenames:
                try:
                    os.remove(os.path.join(target_dir, f))
                    log_func(f"  Old template file deleted: {f}")
                except Exception as e:
                    log_func(f"  Warning: Could not delete {f}: {e}")

def integrate_dx7_data(log_func=print, start_index=None, force_clean=True):
    """
    Kopiert alle DX7-Sysex-Dateien in den Export-Voice-Ordner.
    - start_index: Erster freier Index (wird verwendet, wenn angegeben; sonst 1)
    - force_clean: Wenn True, werden vor dem Kopieren alle alten DX7-Dateien
                   im Ziel gelöscht (basierend auf Basisnamen).
    """
    os.makedirs(TARGET_VOICE_DIR, exist_ok=True)
    os.makedirs(TARGET_LAB_DIR, exist_ok=True)

    log_func("--- DX7 Integration: Copying ROMs and additional Sysex files ---")

    if not os.path.exists(SOURCE_DIR):
        log_func(f"Error: Source folder '{SOURCE_DIR}' not found!")
        return

    # 1. Liste der Quell-Basisnamen (ohne Index) für Bereinigung
    all_source_files = get_sorted_dx7_files()
    if not all_source_files:
        log_func("No .syx files found in DX7 Cartridges folder.")
        return

    source_basenames = {f for f in all_source_files}   # z.B. "rom1a.syx"

    # 2. Bereinigung alter DX7-Voices (wenn gewünscht)
    if force_clean:
        clean_old_dx7_voices(TARGET_VOICE_DIR, source_basenames, log_func)

    # 3. Ermittle bereits verwendete Indizes im Zielordner (nach der Bereinigung)
    used_indices = get_used_indices(TARGET_VOICE_DIR)
    # Falls start_index angegeben, nutze ihn als Start; sonst beginne bei 1
    current_index = start_index if start_index is not None else 1
    # Stelle sicher, dass current_index nicht bereits belegt ist
    while current_index in used_indices:
        current_index += 1

    first_copied_index = None
    copied_count = 0

    # 4. Kopiere alle sortierten Dateien mit fortlaufenden Indizes
    for filename in all_source_files:
        new_index = get_next_free_index(used_indices, start_at=current_index)
        if first_copied_index is None:
            first_copied_index = new_index
        new_name = f"{new_index:06d}_{filename}"
        src_path = os.path.join(SOURCE_DIR, filename)
        dst_path = os.path.join(TARGET_VOICE_DIR, new_name)
        try:
            shutil.copy2(src_path, dst_path)
            log_func(f"  Copied: {filename} -> {new_name}")
            copied_count += 1
            # Aktualisiere current_index für nächste Runde (optional)
            current_index = new_index + 1
        except Exception as e:
            log_func(f"  Error copying {filename}: {e}")

    if copied_count == 0:
        log_func("No new DX7 voices copied.")
        return

    log_func(f"Copied: {copied_count} voice files (first index: {first_copied_index})")

    # 5. Template-INIs (DX7_Single.ini und DX7_Dual.ini) verarbeiten
    template_names = ["DX7 Single.ini", "DX7 Dual.ini"]
    
    # Bereinigung alter Templates
    if force_clean:
        clean_old_templates(TARGET_LAB_DIR, set(template_names), log_func)

    # Ermittle freie Indizes für die INIs (separater Bereich)
    lab_used = get_used_indices(TARGET_LAB_DIR, exclude_suffixes=[])
    bank_num = max(0, first_copied_index - 1)   # BankNumber beginnt bei 0

    for template_name in template_names:
        src_path = os.path.join(SOURCE_DIR, template_name)
        if not os.path.exists(src_path):
            log_func(f"  Note: Template {template_name} missing in source folder.")
            continue

        # Index für diese INI vergeben
        ini_index = get_next_free_index(lab_used, start_at=1)
        new_ini_name = f"{ini_index:06d}_{template_name}"
        dst_path = os.path.join(TARGET_LAB_DIR, new_ini_name)

        try:
            with open(src_path, "r", encoding="utf-8") as f:
                content = f.read()
            # BankNumber anpassen
            new_content = re.sub(r"(BankNumber\d+=)\d+", rf"\g<1>{bank_num}", content)
            with open(dst_path, "w", encoding="utf-8") as f:
                f.write(new_content)
            log_func(f"  Template created: {new_ini_name} (BankNumber={bank_num})")
        except Exception as e:
            log_func(f"  Error with template {template_name}: {e}")

    log_func("--- DX7 Integration complete ---\n")

if __name__ == "__main__":
    # Testaufruf ohne Parameter
    integrate_dx7_data()