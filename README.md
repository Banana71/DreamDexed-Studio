# DreamDexed Studio – The Seed Manager

A Python desktop application (tkinter) for managing performances and voices for
the **Raspberry Pi** running **Circle** and **miniDexed / DreamDexed**. It connects
via FTP, offers an interactive explorer, imports/exports/converts performance
files, generates DX7 voice sheets, and integrates MIDI control.

<img width="1221" height="888" alt="DreamDexed Studio" src="https://github.com/user-attachments/assets/7cd18a21-94e3-4ede-ad3a-1c5763cb73a3" />


## Features

- **FTP Explorer** – Browse and manage `/SD` on the Raspberry Pi, copy/move
  performances, create/rename/delete banks.
- **Workflow** – One‑click import from RPi → convert → export (RPi, GitHub, Dexed).
- **Soundplantage Update** – Download the latest official performances from the
  Soundplantage GitHub repo and synchronise selected banks with your RPi.
- **Performance Editor** – Full TG editor (channel, volume, pan, FX sends, detune,
  note limits, TG link), mixer overview, and voice sheet export.
- **DX7 Voice Data Sheet Generator** – Parse any VoiceData and produce a printable
  Dexed‑style parameter sheet.
- **MIDI Button Navigation** – Use your PC keyboard to control the miniDexed
  buttons (Prev/Next/Select/Home…) via MIDI notes.
- **Program Change Controller** – Type a 3‑digit number and send bank+program
  changes directly from the keyboard.
- **Chord Scanner** – Real‑time chord detection from an external MIDI keyboard
  (Windows only, using `winmm`).
- **Sysex / Bank Conversion** – Convert INI performances to DX7 SysEx banks,
  including automatic DX7 ROM integration.
- **Dynamic GUI Scaling** – Adapts to screen height, configurable in 75–300 %.

## Requirements

- Windows 7 or later (uses `tkinter`, `winmm` for MIDI)
- Python 3.9+ (tested with 3.11)
- Python packages:
  - `Pillow` – for the logo
  - `reportlab` – for PDF generation
  - `requests` – for downloading updates from GitHub
- No additional MIDI libraries needed – MIDI I/O uses the Windows multimedia API
  directly.

Install the dependencies:

```bash
pip install Pillow reportlab requests
```

## Quick Start

1. **Clone the repository** and enter the project folder.
2. Run `Main.py` with Python.
3. In the **Device** dropdown, click **⚙️ Edit Profiles** to create an FTP
   profile for your Raspberry Pi (IP, user, password; defaults: `admin`/`admin`).
4. Select the profile → the Explorer on the right will connect and load the
   Pi’s configuration (`minidexed.ini`).
5. **Workflow**:
   - Click **1. Import from RPi** – choose which banks to download.
   - Click **2. Convert** – extracts sysex, creates PDF, optionally adds DX7 ROMs.
   - Click **3. Export** – uploads everything back to the RPi and/or syncs with
     your local Dexed/GitHub folders.
6. **Performance editing**:
   - Right‑click an `.ini` file in the Explorer tree and choose **F2** or
     double‑click to open the editor.
   - Double‑right‑click to send a Program Change to the Pi.

## MIDI Button Navigation

If `minidexed.ini` has `MIDIButtonNotes=1`, the navigation is automatically
enabled (if a MIDI output device is selected in the config). Use the
**MIDI Button Config** dialog to assign PC keys to the functions.

To send a Program Change, type a 3‑digit number on your keyboard and press
`Enter`. The active channel is read from `PerformanceSelectChannel`.

## Chord Scanner

Select a MIDI input device from the dropdown. Play chords on an external
keyboard; the recognised chord name appears in the main window.

## Configuration

Most paths and options are saved in `config.ini` and `config.json`.
`midi_button_config.json` stores your personal key mappings.

## Project Structure

```text
.
├── Main.py                     # Application entry point
├── config.ini                  # Main configuration
├── config.json                 # FTP profiles
├── midi_button_config.json     # PC key → MIDI function mapping
├── Import/                     # Working directory for imported performances
│   └── performance/
├── Export/                     # Output after conversion
│   ├── performance/
│   ├── sysex/voice/
│   └── Soundplantage/
├── VoiceSheets/                # Generated DX7 data sheets
├── Soundplantage/              # Local mirror of Soundplantage repo
│   └── performance/
├── _backups/                   # Timestamped backups
├── DX7 Cartridges/             # Source folder for additional DX7 ROMs
├── harvester/                  # Application modules
│   ├── constants.py
│   ├── performance_manager.py
│   ├── rename_dialog.py
│   ├── update.py
│   ├── Perf2syx.py
│   ├── perf2sheet.py
│   ├── PerfList_pdf_exp.py
│   ├── DX7_Roms.py
│   ├── chord_scanner.py
│   ├── midi_utils.py
│   ├── midi_button_config_dialog.py
│   ├── minidexed_ini.py
│   ├── ftp_utils.py
│   ├── dialogs.py
│   ├── status.py
│   ├── ini_utils.py
│   └── widgets.py
└── harvester/logo.png
```

## Licence
The source code of DreamDexed Studio is licensed under the MIT License.
See LICENSE for details.

The sound performances and DX7 voices (the .ini files and SysEx banks)
provided by the project or by Soundplantage are free for personal use but
may not be used commercially or redistributed in a way that allows others
to profit from the original DX7 patches. The exact licence terms for the
content will be added separately (e.g., CC BY‑NC 4.0).

## Acknowledgements
- miniDexed by probonopd & team
- Dexed DX7 emulator
- Soundplantage – the official DreamDexed performance library

## Contributing
Pull requests and suggestions are welcome. Please open an issue first to discuss
what you would like to change.
