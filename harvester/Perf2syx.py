# harvester/Perf2syx.py
# =============================================================================
# --- ABSCHNITT 1: IMPORTE UND KONSTANTEN ---
# =============================================================================
import re
from pathlib import Path
from typing import List, Callable, Optional

VOICE_BYTES_BANK = 128
BANK_VOICES = 32
BANK_DATA_LEN = VOICE_BYTES_BANK * BANK_VOICES
SYX_HDR = bytes([0xF0, 0x43, 0x00, 0x09, 0x20, 0x00])
SYX_TAIL = 0xF7

INIT_VOICE_128 = bytes([0x00] * VOICE_BYTES_BANK)

# =============================================================================
# --- ABSCHNITT 2: HILFSFUNKTIONEN ---
# =============================================================================
def yamaha_checksum(data: bytes) -> int:
    s = sum(data) & 0x7F
    return (-s) & 0x7F

def natkey(s: str):
    return [int(t) if t.isdigit() else t.lower() for t in re.findall(r'\d+|\D+', s)]

def discover_inis(indir: Path) -> List[Path]:
    files = list(indir.glob("*.ini"))
    files.sort(key=lambda p: natkey(p.name))
    return files

def extract_perf_name(text: str, fallback_from_filename: str) -> str:
    m = re.search(r'^\s*Name\s*=\s*(.+?)\s*$', text, flags=re.MULTILINE)
    if m:
        name = m.group(1).strip()
    else:
        name = fallback_from_filename
        if "_" in name:
            name = name.split("_", 1)[1]
        if name.lower().endswith(".ini"):
            name = name[:-4]
    name = "".join(ch if 32 <= ord(ch) <= 126 else " " for ch in name)
    return name[:10].ljust(10, " ")

def extract_perf_index(filename: str) -> str:
    m = re.match(r'^(\d+)', filename)
    if m:
        return f"{int(m.group(1)):03d}"
    return "001"

def parse_voice_and_channel(text: str):
    result = []
    for i in range(1, 9):
        mch = re.search(rf"^(?:MIDI\s*Channel|MIDIChannel){i}\s*=\s*(\d+)$", text, flags=re.MULTILINE | re.IGNORECASE)
        ch = int(mch.group(1)) if mch else 0

        m = re.search(rf"^VoiceData{i}\s*=\s*(.+)$", text, flags=re.MULTILINE)
        vbytes = None
        if m:
            parts = [t for t in re.split(r'[\s,;]+', m.group(1).strip()) if t]
            try:
                ba = bytearray()
                for t in parts:
                    b = int(t, 16)
                    if not (0 <= b <= 255):
                        raise ValueError
                    ba.append(b)
                vbytes = bytes(ba)
            except Exception:
                vbytes = None
        result.append((ch, vbytes))
    return result

def single_to_bank128(single: bytes, perf_name_10: str) -> bytes:
    if single is None:
        return None
    if len(single) == 156:
        single = single[:155]
    if len(single) != 155:
        return None

    def op_base(op: int) -> int:
        return {6:0, 5:21, 4:42, 3:63, 2:84, 1:105}[op]

    def get(idx: int) -> int:
        return single[idx]

    out = bytearray(128)
    out_idx = 0

    for op in [6, 5, 4, 3, 2, 1]:
        b = op_base(op)
        for i in range(11): out[out_idx+i] = get(b+i)
        LC = get(b+11) & 0x03
        RC = get(b+12) & 0x03
        out[out_idx+11] = ((RC & 0x03) << 2) | (LC & 0x03)
        DET = get(b+20) & 0x0F
        RS  = get(b+13) & 0x07
        out[out_idx+12] = ((DET & 0x0F) << 3) | (RS & 0x07)
        KVS = get(b+15) & 0x07
        AMS = get(b+14) & 0x03
        out[out_idx+13] = ((KVS & 0x07) << 2) | (AMS & 0x03)
        out[out_idx+14] = get(b+16)
        FC = get(b+18) & 0x1F
        M  = get(b+17) & 0x01
        out[out_idx+15] = (FC << 1) | M
        out[out_idx+16] = get(b+19)
        out_idx += 17

    for i in range(8): out[102+i] = get(126+i)

    out[110] = get(134) & 0x1F
    OKS = get(136) & 0x01
    FB  = get(135) & 0x07
    out[111] = ((OKS & 0x01) << 3) | (FB & 0x07)

    for i in range(4): out[112+i] = get(137+i)

    LPMS = get(143) & 0x07
    LFW  = get(142) & 0x07
    LKS  = get(141) & 0x01
    out[116] = (LPMS << 4) | (LFW << 1) | LKS
    out[117] = get(144)

    name_bytes = bytes(single[145:155])
    if name_bytes == b"INIT VOICE":
        out[118:128] = perf_name_10.encode("ascii", errors="ignore")[:10].ljust(10, b' ')
    else:
        out[118:128] = name_bytes

    return bytes(out)

def update_ini_text(text: str, tg: int, bank: int, voice: int) -> str:
    for key, val in [("BankNumber", bank), ("VoiceNumber", voice)]:
        pattern = rf"^({key}{tg}\s*=).*$"
        if re.search(pattern, text, flags=re.MULTILINE):
            text = re.sub(pattern, rf"\g<1>{val}", text, flags=re.MULTILINE)
        else:
            chan_pattern = rf"^((?:MIDI\s*Channel|MIDIChannel){tg}\s*=.*)$"
            text = re.sub(chan_pattern, rf"{key}{tg}={val}\n\g<1>", text, flags=re.MULTILINE | re.IGNORECASE)
    return text

def update_voicedata_text(text: str, tg: int, new_vbytes: bytes) -> str:
    hex_str = " ".join(f"{b:02X}" for b in new_vbytes)
    pattern = rf"^(VoiceData{tg}\s*=).*$"
    if re.search(pattern, text, flags=re.MULTILINE):
        text = re.sub(pattern, rf"\g<1>{hex_str}", text, flags=re.MULTILINE)
    return text

def guess_bankname(folder: Path) -> str:
    name = folder.name
    if "_" in name:
        return name.split("_", 1)[1]
    return name

# =============================================================================
# --- ABSCHNITT 3: HAUPT-KONVERTIERUNG ---
# =============================================================================
def run_conversion(indir: Path, out_dexed_dir: Path, out_syx_dir: Path, folder_out_perf: Path, start_bank: int, log_callback: Optional[Callable[[str], None]] = None):
    """
    Führt die Konvertierung aus. Nutzt log_callback für die Ausgabe im GUI-Protokollfenster.
    """
    def log(msg: str):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)
            
    log(f"Starting conversion of INI files from: {indir.name}")

    subdirs = [d for d in indir.iterdir() if d.is_dir()]
    if not subdirs and list(indir.glob("*.ini")):
        subdirs = [indir]

    subdirs.sort(key=lambda p: natkey(p.name))

    current_global_bank = start_bank
    total_voices_exported = 0

    for folder in subdirs:
        perf_files = discover_inis(folder)
        if not perf_files:
            continue

        bankname = guess_bankname(folder)
        seen_voices = {}  
        current_chunk = []
        current_bank_filename = ""
        collected_banks = []
        
        # Lege den Performance-Ausgabeordner an
        current_out_perf = folder_out_perf / folder.name if folder != indir else folder_out_perf
        current_out_perf.mkdir(parents=True, exist_ok=True)

        for perf in perf_files:
            text = perf.read_text(encoding="utf-8", errors="replace")
            perf_name_10 = extract_perf_name(text, perf.name)
            perf_idx_str = extract_perf_index(perf.name)
            
            tg_items = parse_voice_and_channel(text)
            out_text = text

            for tg_index, (midich, vbytes) in enumerate(tg_items, start=1):
                if midich == 0 or vbytes is None:
                    continue

                if len(vbytes) >= 155:
                    name_bytes = bytes(vbytes[145:155])
                    if name_bytes == b"INIT VOICE":
                        new_name = perf_name_10.encode("ascii", errors="ignore")[:10].ljust(10, b' ')
                        mut_vbytes = bytearray(vbytes)
                        mut_vbytes[145:155] = new_name
                        vbytes = bytes(mut_vbytes)
                        out_text = update_voicedata_text(out_text, tg_index, vbytes)

                bankv = single_to_bank128(vbytes, perf_name_10)
                if bankv is None:
                    continue

                if bankv not in seen_voices:
                    if len(current_chunk) == BANK_VOICES:
                        collected_banks.append((current_bank_filename, current_chunk))
                        current_global_bank += 1
                        current_chunk = []

                    if len(current_chunk) == 0:
                        current_bank_filename = f"{current_global_bank:06d}_{bankname}.syx"

                    current_chunk.append(bankv)
                    seen_voices[bankv] = (current_global_bank, len(current_chunk))
                    total_voices_exported += 1

                tgt_bank, tgt_voice = seen_voices[bankv]
                out_text = update_ini_text(out_text, tg_index, tgt_bank - 1, tgt_voice)

            out_ini_path = current_out_perf / perf.name
            out_ini_path.write_text(out_text, encoding="utf-8")

        if current_chunk:
            collected_banks.append((current_bank_filename, current_chunk))
            current_global_bank += 1

        for fname, chunk in collected_banks:
            if len(chunk) < BANK_VOICES:
                chunk = chunk + [INIT_VOICE_128] * (BANK_VOICES - len(chunk))
            
            bank_data = b''.join(chunk)
            chk = yamaha_checksum(bank_data)
            syx = SYX_HDR + bank_data + bytes([chk, SYX_TAIL])
            
            (out_syx_dir / fname).write_bytes(syx)
            
            if "_" in fname:
                prefix, rest = fname.split("_", 1)
                dexed_fname = f"{prefix[-3:]}_{rest}"
            else:
                dexed_fname = fname
                
            dexed_path = out_dexed_dir / dexed_fname
            counter = 1
            while dexed_path.exists():
                dexed_path = out_dexed_dir / f"{dexed_fname.replace('.syx', '')}_{counter}.syx"
                counter += 1
                
            dexed_path.write_bytes(syx)
            
            log(f"Created: {fname} & {dexed_path.name} (Voices: {sum(1 for v in chunk if v != INIT_VOICE_128)})")

    log(f"Done! {total_voices_exported} unique voices processed.")
    log("✅ Conversion completed successfully.")

# =============================================================================
# --- ABSCHNITT 4: STANDALONE-AUFRUF (OPTIONAL) ---
# =============================================================================
if __name__ == "__main__":
    # Erlaubt weiterhin das Testen des Skripts ohne GUI
    base_dir = Path(".").resolve()
    run_conversion(
        indir=base_dir / "performance",
        out_dexed_dir=base_dir / "Export" / "Soundplantage",
        out_syx_dir=base_dir / "Export" / "sysex" / "voice",
        folder_out_perf=base_dir / "Export" / "performance",
        start_bank=1
    )