# DreamDexed Studio – The Seed Manager

A Windows desktop application (tkinter) for managing performances and voices for
the **Raspberry Pi** running **Circle** and **miniDexed / DreamDexed**. It connects
via FTP, offers an interactive explorer, imports/exports/converts performance
files, generates DX7 voice sheets, and integrates MIDI control. 

DreamDexed Studio is available both as a **standalone, portable Windows executable** (no installation required) and as a **Python project** for developers.

<img width="1221" height="888" alt="DreamDexed Studio" src="https://github.com/user-attachments/assets/7cd18a21-94e3-4ede-ad3a-1c5763cb73a3" />

*Download latest Portable Windows version - unzip and run `DreamDexed-Studio.exe`*

[![Download EXE](https://img.shields.io/badge/Download-Latest-blue?style=for-the-badge&logo=github)](https://github.com/Banana71/DreamDexed-Studio/releases/latest/download/DreamDexed-Studio.zip)  


## Features

- **FTP Explorer** – Browse and manage `/SD` on the Raspberry Pi, copy/move
  performances, create/rename/delete banks.
- **Workflow** – One‑click import from RPi → convert → export (RPi, GitHub, Dexed).
- **Voice Deduplication & Sysex Export** – During conversion, every performance
  is scanned for its VoiceData. Identical voices are recognised and stored only
  once in standard 32‑voice DX7 Sysex banks. The original performance files are
  updated so that each TG‘s BankNumber and VoiceNumber point to the correct slot
  – no manual tuning needed.
- **Soundplantage Update** – Download the latest official performances from the
  Soundplantage GitHub repo and synchronise selected banks with your RPi.
- **Performance Editor** – Essential TG editor (channel, volume, pan, FX sends, detune,
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

## Requirements & installation

### Option A: Portable Windows Version (Recommended)
- Windows 7 or later.
- **No dependencies required.** - Simply download the latest `DreamDexed-Studio.zip` from the Releases page, extract the archive, and run `DreamDexed-Studio.exe`.

### Option B: Running from Source (Python)
- Windows 7 or later – uses `tkinter` and the built‑in Windows Multimedia API
  (`winmm`) for MIDI I/O. **No extra MIDI driver or library is needed.**
- Python 3.9+ (tested with 3.11)
- Required Python packages are listed in `requirements.txt`

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Quick Start

1. **Launch the application**:
   - **Portable:** Double-click `DreamDexed-Studio.exe`.
   - **Source:** Run `Main.py` with Python.
2. In the **Device** dropdown, click **⚙️ Edit Profiles** to create an FTP profile for your Raspberry Pi (IP, user, password; defaults: `admin`/`admin`).
3. Select the profile → the Explorer on the right will connect and load the Pi’s configuration (`minidexed.ini`).
4. **Workflow**:
   - Click **1. Import from RPi** – choose which banks to download.
   - Click **2. Convert** – extracts sysex, creates PDF, optionally adds DX7 ROMs.
   - Click **3. Export** – uploads everything back to the RPi and/or syncs with your local Dexed/GitHub folders.
5. **Performance editing**:
   - Right‑click an `.ini` file in the Explorer tree and choose **F2** or double‑click to open the editor.
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
│   ├── about_dialog.py
│   ├── chord_scanner.py
│   ├── constants.py
│   ├── dialogs.py
│   ├── DX7_Roms.py
│   ├── ftp_client.py
│   ├── ftp_utils.py
│   ├── ini_utils.py
│   ├── midi_button_config_dialog.py
│   ├── midi_utils.py
│   ├── minidexed_ini.py
│   ├── mixer_dialog.py
│   ├── perf2sheet.py
│   ├── Perf2syx.py
│   ├── PerfList_pdf_exp.py
│   ├── performance_manager.py
│   ├── rename_dialog.py
│   ├── soundplantage_update.py
│   ├── status.py
│   ├── update.py
│   └── widgets.py
└── harvester/logo.png
```

## Licence

This repository contains two different types of works with separate licences:

**Software (source code)**
All Python files, GUI code, and scripts are licensed under the **MIT License**.
See [LICENSE](LICENSE) for the full text.

**Sound content (performances & voice patches)**
The `.ini` performance files and `.syx` voice banks included in the
`Soundplantage/`, `Export/` and `Import/` folders are
provided under the **DreamDexed Performance License (DPL)**.
See [LICENSE-CONTENT.md](LICENSE-CONTENT.md) for details.

In short:
- The **software** may be freely used, modified, and redistributed.
- The **performances** are free for any use, including commercial projects.
- **Extracting and selling the isolated DX7 voice patches** is not permitted.
