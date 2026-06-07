"""
minidexed_ini.py – Parser for /SD/minidexed.ini on the Raspberry Pi.
Extracts MIDI button notes, channels and flags for the controller integration.
"""


def parse_minidexed_ini(text: str) -> dict:
    """
    Parse a miniDexed INI file and return a dictionary:

    {
        "midi_button_ch": int,               # MIDI channel for button notes (0=off)
        "midi_button_notes": int,            # 0 or 1 (note mode on/off)
        "performance_select_channel": int,   # Channel for program change, 0=disabled
        "buttons": [
            {
                "function": str,             # e.g. "Prev", "Next", "Home", ...
                "note": int,                 # MIDI note number
                "action": str                # original action from INI (optional)
            },
            ...
        ]
    }

    Missing keys get sensible defaults.
    """

    config = {
        "midi_button_ch": 0,
        "midi_button_notes": 0,
        "performance_select_channel": 0,
        "master_volume": 127,
        "buttons": []
    }

    # Simple key mappings (exact match)
    simple_keys = {
        "MIDIButtonCh": "midi_button_ch",
        "MIDIButtonNotes": "midi_button_notes",
        "PerformanceSelectChannel": "performance_select_channel",
        "MasterVolume": "master_volume",
    }

    # Temporary storage for actions
    actions = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        # Simple keys
        if key in simple_keys:
            try:
                config[simple_keys[key]] = int(value)
            except ValueError:
                pass
            continue

        # MIDIButtonAction...
        if key.startswith("MIDIButtonAction"):
            func_name = key[len("MIDIButtonAction"):]  # e.g. "Prev"
            actions[func_name] = value
            continue

        # MIDIButton... (not Ch, Notes, Action)
        if key.startswith("MIDIButton"):
            # Skip the special ones already handled
            if key in ("MIDIButtonCh", "MIDIButtonNotes"):
                continue
            func_name = key[len("MIDIButton"):]   # e.g. "Prev", "Next"
            try:
                note = int(value)
                if 0 <= note <= 127:
                    config["buttons"].append({
                        "function": func_name,
                        "note": note,
                        "action": actions.get(func_name, "")
                    })
            except ValueError:
                pass
            continue

    return config