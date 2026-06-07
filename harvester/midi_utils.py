"""
midi_utils.py – MIDI output helper for DreamDexed Studio.
Uses ctypes + winmm.dll to list MIDI output devices, send
Bank Select (CC0) + Program Change messages, and SysEx (e.g. Master Volume).
"""

import ctypes
from ctypes import wintypes
import time

# ---------- Windows MIDI Out API ----------
MAXPNAMELEN = 32
MMSYSERR_NOERROR = 0

class MIDIOUTCAPS(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("vDriverVersion", wintypes.DWORD),
        ("szPname", wintypes.CHAR * MAXPNAMELEN),
        ("wTechnology", wintypes.WORD),
        ("wVoices", wintypes.WORD),
        ("wNotes", wintypes.WORD),
        ("wChannelMask", wintypes.DWORD),
        ("dwSupport", wintypes.DWORD),
    ]

# --- MIDIHDR for SysEx / long messages ---
class MIDIHDR(ctypes.Structure):
    _fields_ = [
        ("lpData", wintypes.LPSTR),
        ("dwBufferLength", wintypes.DWORD),
        ("dwBytesRecorded", wintypes.DWORD),
        ("dwUser", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("lpNext", wintypes.LPVOID),
        ("reserved", wintypes.DWORD),
        ("dwOffset", wintypes.DWORD),
        ("dwReserved", ctypes.POINTER(wintypes.DWORD) * 8),
    ]

winmm = ctypes.windll.winmm

# --- Device enumeration ---
winmm.midiOutGetNumDevs.argtypes = []
winmm.midiOutGetNumDevs.restype = wintypes.UINT

winmm.midiOutGetDevCapsA.argtypes = [wintypes.UINT, ctypes.POINTER(MIDIOUTCAPS), wintypes.UINT]
winmm.midiOutGetDevCapsA.restype = wintypes.DWORD

# --- Short messages (Note, CC, PC) ---
winmm.midiOutOpen.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.UINT,
                              ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
winmm.midiOutOpen.restype = wintypes.DWORD

winmm.midiOutShortMsg.argtypes = [wintypes.HANDLE, wintypes.DWORD]
winmm.midiOutShortMsg.restype = wintypes.DWORD

winmm.midiOutClose.argtypes = [wintypes.HANDLE]
winmm.midiOutClose.restype = wintypes.DWORD

# --- Long messages (SysEx) ---
winmm.midiOutPrepareHeader.argtypes = [wintypes.HANDLE, ctypes.POINTER(MIDIHDR), wintypes.UINT]
winmm.midiOutPrepareHeader.restype = wintypes.DWORD

winmm.midiOutUnprepareHeader.argtypes = [wintypes.HANDLE, ctypes.POINTER(MIDIHDR), wintypes.UINT]
winmm.midiOutUnprepareHeader.restype = wintypes.DWORD

winmm.midiOutLongMsg.argtypes = [wintypes.HANDLE, ctypes.POINTER(MIDIHDR), wintypes.UINT]
winmm.midiOutLongMsg.restype = wintypes.DWORD


def list_midi_out_devices():
    """Gibt eine Liste aller verfügbaren MIDI‑Ausgabegeräte zurück."""
    num = winmm.midiOutGetNumDevs()
    devices = []
    for i in range(num):
        caps = MIDIOUTCAPS()
        if winmm.midiOutGetDevCapsA(i, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR:
            name = caps.szPname.decode('ascii', errors='replace').strip()
            devices.append(name)
        else:
            devices.append(f"Unknown Device {i}")
    return devices


def send_bank_and_program(device_index, channel, bank, program):
    """
    Sendet Bank Select (CC0 + CC32) und Program Change an das angegebene MIDI‑Ausgabegerät.
    device_index: Index des Ausgabegeräts (0‑basiert)
    channel: MIDI‑Kanal (1‑16)
    bank: Bank‑Nummer (0‑127)
    program: Programm‑Nummer (0‑127)
    """
    if not (0 <= bank <= 127 and 0 <= program <= 127 and 1 <= channel <= 16):
        raise ValueError("Bank, Program (0-127) oder Channel (1-16) ungültig.")

    handle = wintypes.HANDLE()
    result = winmm.midiOutOpen(ctypes.byref(handle), device_index, 0, 0, 0)
    if result != MMSYSERR_NOERROR:
        raise RuntimeError(f"Konnte MIDI‑Ausgabegerät {device_index} nicht öffnen (Fehler {result}).")

    try:
        cc_status = 0xB0 | (channel - 1)

        # Bank Select MSB (CC 0)
        msb = (bank >> 7) & 0x7F
        msb_msg = cc_status | (0 << 8) | (msb << 16)
        winmm.midiOutShortMsg(handle, msb_msg)

        # Bank Select LSB (CC 32)
        lsb = bank & 0x7F
        lsb_msg = cc_status | (32 << 8) | (lsb << 16)
        winmm.midiOutShortMsg(handle, lsb_msg)

        # Program Change
        pc_status = 0xC0 | (channel - 1)
        pc_msg = pc_status | (program << 8)
        winmm.midiOutShortMsg(handle, pc_msg)
    finally:
        winmm.midiOutClose(handle)


def send_sysex(device_index, data_bytes):
    """
    Send a raw SysEx message to the given MIDI output device.
    data_bytes: list or bytes of the complete SysEx message (e.g. including F0 and F7).
    """
    if not (0 <= device_index < winmm.midiOutGetNumDevs()):
        raise RuntimeError(f"Invalid device index {device_index}")

    handle = wintypes.HANDLE()
    result = winmm.midiOutOpen(ctypes.byref(handle), device_index, 0, 0, 0)
    if result != 0:
        raise RuntimeError(f"Failed to open MIDI device (error {result})")

    try:
        # Pack bytes into a ctypes buffer
        buf = (ctypes.c_ubyte * len(data_bytes))(*data_bytes)
        hdr = MIDIHDR()
        hdr.lpData = ctypes.cast(buf, wintypes.LPSTR)
        hdr.dwBufferLength = len(data_bytes)
        hdr.dwFlags = 0

        # Prepare header
        winmm.midiOutPrepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
        # Send long message
        result = winmm.midiOutLongMsg(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
        if result != 0:
            raise RuntimeError(f"midiOutLongMsg failed (error {result})")
        # Brief wait for completion
        time.sleep(0.02)
        # Unprepare
        winmm.midiOutUnprepareHeader(handle, ctypes.byref(hdr), ctypes.sizeof(hdr))
    finally:
        winmm.midiOutClose(handle)