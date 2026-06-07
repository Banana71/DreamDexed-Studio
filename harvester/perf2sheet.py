# harvester/perf2sheet.py
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DX7 Voice Data Sheet Generator (MiniDexed Performance Edition)
---------------------------------------------------------------
Reads a MiniDexed/DreamDexed Performance .ini file,
extracts the 155/156‑byte VoiceData of a selected TG
and generates a human-readable datasheet in Dexed style.
"""

import sys
import os
import re
import math

# --- Complete constants (from dx7sheet.py) ---
NOTE_NAMES = [
    'A-1', 'A#-1', 'B-1', 'C0', 'C#0', 'D0', 'D#0', 'E0', 'F0', 'F#0', 'G0', 'G#0',
    'A0', 'A#0', 'B0', 'C1', 'C#1', 'D1', 'D#1', 'E1', 'F1', 'F#1', 'G1', 'G#1',
    'A1', 'A#1', 'B1', 'C2', 'C#2', 'D2', 'D#2', 'E2', 'F2', 'F#2', 'G2', 'G#2',
    'A2', 'A#2', 'B2', 'C3', 'C#3', 'D3', 'D#3', 'E3', 'F3', 'F#3', 'G3', 'G#3',
    'A3', 'A#3', 'B3', 'C4', 'C#4', 'D4', 'D#4', 'E4', 'F4', 'F#4', 'G4', 'G#4',
    'A4', 'A#4', 'B4', 'C5', 'C#5', 'D5', 'D#5', 'E5', 'F5', 'F#5', 'G5', 'G#5',
    'A5', 'A#5', 'B5', 'C6', 'C#6', 'D6', 'D#6', 'E6', 'F6', 'F#6', 'G6', 'G#6',
    'A6', 'A#6', 'B6', 'C7', 'C#7', 'D7', 'D#7', 'E7', 'F7', 'F#7', 'G7', 'G#7',
    'A7', 'A#7', 'B7', 'C8'
]
CURVE_MODES = {0: '-LIN', 1: '-EXP', 2: '+EXP', 3: '+LIN'}
LFO_WAVES = {0: 'TRIANGLE', 1: 'SAW UP', 2: 'SAW DOWN', 3: 'SQUARE', 4: 'SINE', 5: 'S+HOLD'}


def parse_voice_155(data):
    """
    Parses 155 or 156 bytes of MiniDexed VoiceData directly.
    Uses exactly the offsets/bitmasks from minidexed2syx.py.
    """
    if len(data) == 156:
        data = data[:155]
    if len(data) != 155:
        raise ValueError(f"VoiceData must be 155 or 156 bytes long, got {len(data)}")

    def get(idx): return data[idx]

    params = {'ops': []}

    # Offsets per operator: 21 bytes, starting at 0,21,42,63,84,105
    # Order OP1..OP6 (descending, so that OP1 corresponds to the highest offset)
    op_offsets = [105, 84, 63, 42, 21, 0]

    for base in op_offsets:
        op = {}

        # Envelope Rates (bytes 0..3) and Levels (bytes 4..7)
        op['eg_rate']  = [get(base+0), get(base+1), get(base+2), get(base+3)]
        op['eg_level'] = [get(base+4), get(base+5), get(base+6), get(base+7)]

        # Keyboard Scaling
        bp = get(base+8)
        op['breakpoint'] = NOTE_NAMES[bp] if 0 <= bp < len(NOTE_NAMES) else 'N/A'
        op['l_depth'] = get(base+9)
        op['r_depth'] = get(base+10)

        # Left/Right Curve: bits 0-1 of byte 11 and byte 12
        lc = get(base+11) & 0x03
        rc = get(base+12) & 0x03
        op['l_curve'] = CURVE_MODES[lc]
        op['r_curve'] = CURVE_MODES[rc]

        # Rate Scaling: bits 0-2 of byte 13
        op['rate_scaling'] = get(base+13) & 0x07

        # Amp Mod Sens: bits 0-1 of byte 14
        op['amp_mod_sens'] = get(base+14) & 0x03
        # Key Velocity Sens: bits 0-2 of byte 15
        op['key_vel_sens'] = get(base+15) & 0x07

        # Output Level: byte 16
        op['level'] = get(base+16)

        # Oscillator Mode: bit 0 of byte 17
        mode_bit = get(base+17) & 0x01
        op['mode'] = 'FIX' if mode_bit else 'RATIO'

        # Frequency Coarse: lower 5 bits of byte 18
        coarse_raw = get(base+18) & 0x1F
        fine_raw = get(base+19)
        op['coarse_display'] = coarse_raw
        op['fine_raw'] = fine_raw

        # Frequency calculation
        if op['mode'] == 'RATIO':
            base_ratio = 0.5 if coarse_raw == 0 else float(coarse_raw)
            op['coarse_display'] = base_ratio
            calculated_val = base_ratio * (1.0 + fine_raw / 100.0)
            op['freq_string'] = f"{calculated_val:.2f}"
        else:  # FIXED
            exponent = (coarse_raw % 4) + fine_raw / 100.0
            calculated_val = math.pow(10, exponent)
            if calculated_val >= 1000:
                op['freq_string'] = f"{calculated_val:.2f}"
            elif calculated_val >= 100:
                op['freq_string'] = f"{calculated_val:.3f}"
            elif calculated_val >= 10:
                op['freq_string'] = f"{calculated_val:.4f}"
            else:
                op['freq_string'] = f"{calculated_val:.5f}"

        # Detune: bits 3-6 of byte 20
        det_raw = get(base+20) & 0x0F
        op['detune'] = det_raw - 7

        params['ops'].append(op)

    # Global parameters from offset 126
    params['pitch_eg_rate']  = [get(126), get(127), get(128), get(129)]
    params['pitch_eg_level'] = [get(130), get(131), get(132), get(133)]

    params['algorithm'] = (get(134) & 0x1F) + 1
    params['feedback'] = get(135) & 0x07
    params['osc_sync'] = 'ON' if (get(136) & 0x01) else 'OFF'

    params['lfo_speed'] = get(137)
    params['lfo_delay'] = get(138)
    params['lfo_pmd']   = get(139)
    params['lfo_amd']   = get(140)

    params['lfo_sync'] = 'ON' if (get(141) & 0x01) else 'OFF'
    wave_idx = (get(142) >> 1) & 0x07
    params['lfo_wave'] = LFO_WAVES.get(wave_idx, 'UNKNOWN')
    # P Mod Sens: bits 0-2 of byte 143
    params['p_mod_sens'] = get(143) & 0x07

    params['transpose'] = get(144) - 24

    name_bytes = data[145:155]
    params['name'] = name_bytes.decode('ascii', errors='ignore').strip('\x00').strip()

    return params


def create_op_row(label, values):
    return f"{label:<14} " + " ".join(f"{str(v):<7}" for v in values)


def generate_datasheet(params, bank_name, voice_num, bank_num=None, perf_num=None, perf_name=None):
    ops = params['ops']
    sheet = []
    sheet.append("="*62)
    sheet.append("          DX7 VOICE DATA SHEET by SOUNDPLANTAGE.COM")
    sheet.append("="*62)
    
    # New line in the desired format
    if bank_num is not None and perf_num is not None and perf_name is not None:
        sheet.append(f"Performance: {bank_num:03d}:{perf_num:03d} {perf_name} - TG{voice_num} - {params['name']}")
    else:
        # Fallback for old calls
        sheet.append(f"TG{voice_num:02d}: {params['name']}     Performance: {bank_name}")
    
    sheet.append("="*62)
    sheet.append(f"ALGORITHM: {params['algorithm']:<4} FEEDBACK: {params['feedback']:<4} TRANSPOSE: {params['transpose']}")
    sheet.append("-"*62)
    sheet.append(f"{'PARAM':<14} {'OP1':<7} {'OP2':<7} {'OP3':<7} {'OP4':<7} {'OP5':<7} {'OP6':<7}")
    sheet.append("-" * 62)

    sheet.append(create_op_row("OSC MODE", [op['mode'] for op in ops]))
    sheet.append(create_op_row("COARSE", [f"{op['coarse_display']}" for op in ops]))
    sheet.append(create_op_row("FINE (FREQ)", [op['freq_string'] for op in ops]))
    sheet.append(create_op_row("DETUNE", [f"{op['detune']:+d}" for op in ops]))
    sheet.append("-" * 62)

    sheet.append(create_op_row("AMP MOD SENS", [op['amp_mod_sens'] for op in ops]))
    sheet.append(create_op_row("VEL SENS", [op['key_vel_sens'] for op in ops]))
    sheet.append(create_op_row("OUT LEVEL", [op['level'] for op in ops]))
    sheet.append("-" * 62)

    sheet.append(create_op_row("BREAK POINT", [op['breakpoint'] for op in ops]))
    sheet.append(create_op_row("L DEPTH", [op['l_depth'] for op in ops]))
    sheet.append(create_op_row("R DEPTH", [op['r_depth'] for op in ops]))
    sheet.append(create_op_row("L CURVE", [op['l_curve'] for op in ops]))
    sheet.append(create_op_row("R CURVE", [op['r_curve'] for op in ops]))
    sheet.append(create_op_row("RATE SCALING", [op['rate_scaling'] for op in ops]))
    sheet.append("-" * 62)

    for l in range(1, 5):
        sheet.append(create_op_row(f"EG LEVEL {l}", [op['eg_level'][l-1] for op in ops]))
    sheet.append(" " * 3)
    for r in range(1, 5):
        sheet.append(create_op_row(f"EG RATE {r}", [op['eg_rate'][r-1] for op in ops]))

    sheet.append("="*62)
    sheet.append("                   LFO, PITCH EG & SYNC")
    sheet.append("="*62)
    sheet.append(f"LFO WAVE: {params['lfo_wave']:<10} SPEED: {params['lfo_speed']:<5} DELAY: {params['lfo_delay']}")
    sheet.append(f"PMD: {params['lfo_pmd']:<10} AMD: {params['lfo_amd']:<7} P MOD SENS: {params['p_mod_sens']}")
    sheet.append(f"LFO SYNC: {params['lfo_sync']:<9} OSC SYNC: {params['osc_sync']}")
    sheet.append("-" * 62)
    p_rates = params['pitch_eg_rate']
    p_levels = params['pitch_eg_level']
    sheet.append(f"PITCH EG LEVEL: L1={p_levels[0]:<3} L2={p_levels[1]:<3} L3={p_levels[2]:<3} L4={p_levels[3]}")
    sheet.append(f"PITCH EG RATE : R1={p_rates[0]:<3} R2={p_rates[1]:<3} R3={p_rates[2]:<3} R4={p_rates[3]}")
    sheet.append("="*62)
    return "\n".join(sheet)


def sanitize_filename(name):
    name = name.replace('\x00', '').strip()
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


def parse_ini_for_tg(ini_text, tg_num):
    m = re.search(rf"^MIDIChannel{tg_num}\s*=\s*(\d+)", ini_text, re.MULTILINE | re.IGNORECASE)
    if not m:
        m = re.search(rf"^MIDI\s*Channel{tg_num}\s*=\s*(\d+)", ini_text, re.MULTILINE | re.IGNORECASE)
    midich = int(m.group(1)) if m else 0
    if midich == 0:
        return 0, None

    m = re.search(rf"^VoiceData{tg_num}\s*=\s*(.+)$", ini_text, re.MULTILINE | re.IGNORECASE)
    if not m:
        return 0, None
    hex_str = m.group(1).strip()
    parts = [t for t in re.split(r'[\s,;]+', hex_str) if t]
    try:
        ba = bytearray()
        for p in parts:
            ba.append(int(p, 16))
        vbytes = bytes(ba)
        if len(vbytes) not in (155, 156):
            return 0, None
        return midich, vbytes
    except Exception:
        return 0, None


def get_voice_name_from_155(data_155):
    try:
        name = data_155[145:155].decode('ascii', errors='ignore').strip('\x00').strip()
    except:
        name = ""
    return name if name else "NO_NAME"


def main():
    try:
        ini_files = sorted([f for f in os.listdir('.') if f.lower().endswith('.ini')])
        if not ini_files:
            print("Error: No .ini files found in the current directory.")
            input("Press Enter to exit...")
            sys.exit(1)

        print("--- DX7 Voice Data Sheet Generator (MiniDexed Performance) ---")
        print("Available .ini files:")
        print("-" * 40)
        for i, fname in enumerate(ini_files, 1):
            print(f"  {i:02d}: {fname}")
        print("-" * 40)

        file_choice = -1
        while not (1 <= file_choice <= len(ini_files)):
            try:
                file_choice = int(input(f"Which file to load? (1-{len(ini_files)}): "))
            except ValueError:
                pass

        inipath = ini_files[file_choice - 1]
        bank_name = os.path.basename(inipath)
        if re.match(r'^\d{6}_', bank_name):
            bank_name = bank_name[3:]

        with open(inipath, 'r', encoding='utf-8', errors='replace') as f:
            ini_content = f.read()

        valid_tgs = []
        for tg in range(1, 9):
            midich, vbytes = parse_ini_for_tg(ini_content, tg)
            if midich != 0 and vbytes is not None:
                name = get_voice_name_from_155(vbytes)
                valid_tgs.append((tg, name, vbytes))

        if not valid_tgs:
            print("No valid TG with VoiceData found in this file.")
            input("Press Enter to exit...")
            sys.exit(1)

        print("\nValid TGs in this performance:")
        for tg, name, _ in valid_tgs:
            print(f"  TG{tg}: {name}")

        tg_choice = -1
        valid_nums = [t[0] for t in valid_tgs]
        while tg_choice not in valid_nums:
            try:
                tg_choice = int(input(f"Which TG to export? ({', '.join(map(str, valid_nums))}): "))
            except ValueError:
                pass

        selected_vbytes = next(v for tg, _, v in valid_tgs if tg == tg_choice)

        params = parse_voice_155(selected_vbytes)
        datasheet = generate_datasheet(params, bank_name, tg_choice)

        output_dir = "Sheet"
        os.makedirs(output_dir, exist_ok=True)
        safe_name = sanitize_filename(params['name'])
        filename = f"{safe_name}.txt"
        full_path = os.path.join(output_dir, filename)

        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(datasheet)
        print(f"\n--- Datasheet created! ---")
        print(datasheet)
        print(f"\nSaved as: '{full_path}'")

    except Exception as e:
        print(f"\nAn unexpected error occurred:\n{e}")
    finally:
        input("\nPress Enter to exit...")


if __name__ == '__main__':
    main()