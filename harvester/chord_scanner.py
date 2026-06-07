"""
chord_scanner.py – Windows MIDI chord detection for DreamDexed Studio.
Uses ctypes + winmm.dll to read the first available MIDI input device,
detects the most likely chord from currently held notes,
and reports the chord name via a callback (GUI thread).

Includes an 80 ms debounce to avoid flickering when notes are released
during chord changes.
"""

import ctypes
from ctypes import wintypes
import threading
import queue

# ---------- Akkord-Logik (aus dem Chord-Scanner HTML) ----------

PITCH_CLASSES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

FLAT_MAP = {
    'C#': 'D♭', 'D#': 'E♭', 'F#': 'G♭', 'G#': 'A♭', 'A#': 'B♭',
    'C♯': 'D♭', 'D♯': 'E♭', 'F♯': 'G♭', 'G♯': 'A♭', 'A♯': 'B♭',
    'Db': 'D♭', 'Eb': 'E♭', 'Gb': 'G♭', 'Ab': 'A♭', 'Bb': 'B♭'
}

CHORD_PATTERNS = [
    ('',            [0, 4, 7]),
    ('m',           [0, 3, 7]),
    ('sus2',        [0, 2, 7]),
    ('sus4',        [0, 5, 7]),
    ('dim',         [0, 3, 6]),
    ('aug',         [0, 4, 8]),
    ('6',           [0, 4, 7, 9]),
    ('m6',          [0, 3, 7, 9]),
    ('maj7',        [0, 4, 7, 11]),
    ('7',           [0, 4, 7, 10]),
    ('m7',          [0, 3, 7, 10]),
    ('m(maj7)',     [0, 3, 7, 11]),
    ('m7♭5',        [0, 3, 6, 10]),
    ('dim7',        [0, 3, 6, 9]),
    ('7sus4',       [0, 5, 7, 10]),
    ('7sus2',       [0, 2, 7, 10]),
    ('add9',        [0, 2, 4, 7]),
    ('madd9',       [0, 2, 3, 7]),
    ('maj7♭5',      [0, 4, 6, 11]),
    ('7♭5',         [0, 4, 6, 10]),
    ('7♯5',         [0, 4, 8, 10]),
    ('maj7♯11',     [0, 4, 6, 7, 11]),
    ('9',           [0, 2, 4, 7, 10]),
    ('maj9',        [0, 2, 4, 7, 11]),
    ('m9',          [0, 2, 3, 7, 10]),
    ('7♭9',         [0, 1, 4, 7, 10]),
    ('7♯9',         [0, 3, 4, 7, 10]),
    ('6/9',         [0, 2, 4, 7, 9]),
    ('m6/9',        [0, 2, 3, 7, 9]),
    ('9sus4',       [0, 2, 5, 7, 10]),
]

SORTED_PATTERNS = sorted(CHORD_PATTERNS, key=lambda x: len(x[1]))


def _midi_to_pitch_class(midi_note):
    return PITCH_CLASSES[midi_note % 12]


def _pitch_class_to_number(pc):
    normalized = pc.replace('♯', '#').replace('♭', 'b')
    if normalized == 'Db': normalized = 'C#'
    elif normalized == 'Eb': normalized = 'D#'
    elif normalized == 'Gb': normalized = 'F#'
    elif normalized == 'Ab': normalized = 'G#'
    elif normalized == 'Bb': normalized = 'A#'
    if normalized in PITCH_CLASSES:
        return PITCH_CLASSES.index(normalized)
    return -1


def _beautify_chord(raw):
    if '/' in raw:
        chord_part, bass_part = raw.split('/', 1)
        return _beautify_chord(chord_part) + '/' + _to_flat(bass_part)
    for i, ch in enumerate(raw):
        if ch.isalpha() and i > 0:
            root = raw[:i]
            suffix = raw[i:]
            break
    else:
        root = raw
        suffix = ''
    root = _to_flat(root)
    suffix = suffix.replace('#', '♯').replace('b', '♭')
    return root + suffix


def _to_flat(pc):
    normal = pc.replace('#', '♯').replace('b', '♭')
    return FLAT_MAP.get(normal, normal)


def _detect_all_chords(midi_notes):
    unique_pcs = list(dict.fromkeys(map(_midi_to_pitch_class, midi_notes)))
    if len(unique_pcs) < 3:
        return []
    exact = []
    for root_pc in unique_pcs:
        intervals = [0]
        for pc in unique_pcs:
            if pc == root_pc:
                continue
            diff = _pitch_class_to_number(pc) - _pitch_class_to_number(root_pc)
            if diff < 0:
                diff += 12
            intervals.append(diff)
        intervals.sort()
        for name, pattern in CHORD_PATTERNS:
            if intervals == pattern:
                exact.append(root_pc + name)
                break
    if exact:
        return exact
    subset = []
    for root_pc in unique_pcs:
        played = []
        for pc in unique_pcs:
            if pc == root_pc:
                continue
            diff = _pitch_class_to_number(pc) - _pitch_class_to_number(root_pc)
            if diff < 0:
                diff += 12
            played.append(diff)
        played.sort()
        for name, pattern in SORTED_PATTERNS:
            if all(interval in pattern for interval in played):
                subset.append(root_pc + name)
                break
    return subset


def _select_main_chord(all_chords, midi_notes):
    if not all_chords:
        return None
    bass_pc = _midi_to_pitch_class(midi_notes[0])
    first = all_chords[0]
    root = first[0]
    if len(first) > 1 and first[1] in ('#', '♯', 'b', '♭'):
        root = first[:2]
    if _pitch_class_to_number(root) != _pitch_class_to_number(bass_pc):
        return first + '/' + bass_pc
    return first


def detect_chord(active_notes):
    if len(active_notes) < 3:
        return None
    midi_notes = sorted(active_notes)
    all_chords = _detect_all_chords(midi_notes)
    main = _select_main_chord(all_chords, midi_notes)
    if main:
        return _beautify_chord(main)
    return None


# ---------- Windows MIDI via ctypes ----------

MMSYSERR_NOERROR = 0
CALLBACK_FUNCTION = 0x30000
MAXPNAMELEN = 32

class MIDIINCAPS(ctypes.Structure):
    _fields_ = [
        ("wMid", wintypes.WORD),
        ("wPid", wintypes.WORD),
        ("vDriverVersion", wintypes.DWORD),
        ("szPname", wintypes.CHAR * MAXPNAMELEN),
        ("dwSupport", wintypes.DWORD),
    ]

MIDIINPROC = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.UINT,
                                ctypes.c_size_t, wintypes.DWORD, wintypes.DWORD)

winmm = ctypes.windll.winmm
winmm.midiInGetNumDevs.argtypes = []
winmm.midiInGetNumDevs.restype = wintypes.UINT

winmm.midiInOpen.argtypes = [ctypes.POINTER(wintypes.HANDLE), wintypes.UINT,
                             ctypes.c_size_t, ctypes.c_size_t, wintypes.DWORD]
winmm.midiInOpen.restype = wintypes.DWORD

winmm.midiInStart.argtypes = [wintypes.HANDLE]
winmm.midiInStart.restype = wintypes.DWORD

winmm.midiInStop.argtypes = [wintypes.HANDLE]
winmm.midiInStop.restype = wintypes.DWORD

winmm.midiInClose.argtypes = [wintypes.HANDLE]
winmm.midiInClose.restype = wintypes.DWORD

winmm.midiInGetDevCapsA = winmm.midiInGetDevCapsA
winmm.midiInGetDevCapsA.argtypes = [wintypes.UINT, ctypes.POINTER(MIDIINCAPS), wintypes.UINT]
winmm.midiInGetDevCapsA.restype = wintypes.DWORD


class ChordScanner:
    @staticmethod
    def list_devices():
        """Gibt eine Liste aller verfügbaren MIDI‑Eingabegeräte zurück."""
        num = winmm.midiInGetNumDevs()
        devices = []
        for i in range(num):
            caps = MIDIINCAPS()
            if winmm.midiInGetDevCapsA(i, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR:
                name = caps.szPname.decode('ascii', errors='replace').strip()
                devices.append(name)
            else:
                devices.append(f"Unknown Device {i}")
        return devices

    @staticmethod
    def probe_device():
        """Ermittelt den Namen des ersten MIDI‑Eingangs, ohne dauerhaft zu öffnen.
        Rückgabe: (Anzahl der Geräte, Name) oder (0, None)."""
        num = winmm.midiInGetNumDevs()
        if num == 0:
            return 0, None
        caps = MIDIINCAPS()
        if winmm.midiInGetDevCapsA(0, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR:
            name = caps.szPname.decode('ascii', errors='replace').strip()
            return num, name
        return num, None

    def __init__(self, root, callback, device_index=0):
        self.root = root
        self.callback = callback
        self.device_index = device_index
        self.hmidi = None
        self.device_name = None
        self._active_notes = {}
        self._lock = threading.Lock()
        self._midi_callback = MIDIINPROC(self._on_midi_event)

        self._queue = queue.Queue()
        self._debounce_timer = None
        self._poll_id = None

    def start(self):
        num_devs = winmm.midiInGetNumDevs()
        if self.device_index >= num_devs or self.device_index < 0:
            self.callback("MIDI Err")
            return
        handle = wintypes.HANDLE()
        result = winmm.midiInOpen(ctypes.byref(handle), self.device_index,
                                  ctypes.cast(self._midi_callback, ctypes.c_void_p).value,
                                  0, CALLBACK_FUNCTION)
        if result != MMSYSERR_NOERROR:
            self.callback("MIDI Err")
            return
        self.hmidi = handle
        winmm.midiInStart(self.hmidi)

        caps = MIDIINCAPS()
        if winmm.midiInGetDevCapsA(self.device_index, ctypes.byref(caps), ctypes.sizeof(caps)) == MMSYSERR_NOERROR:
            self.device_name = caps.szPname.decode('ascii', errors='replace').strip()
        else:
            self.device_name = "Unknown"

        self._start_poller()

    def stop(self):
        if self.hmidi:
            winmm.midiInStop(self.hmidi)
            winmm.midiInClose(self.hmidi)
            self.hmidi = None
        if self._poll_id:
            self.root.after_cancel(self._poll_id)
            self._poll_id = None
        if self._debounce_timer:
            self.root.after_cancel(self._debounce_timer)
            self._debounce_timer = None

    def get_device_name(self):
        return self.device_name

    def _start_poller(self):
        self._poll_queue()
        self._poll_id = self.root.after(20, self._start_poller)

    def _poll_queue(self):
        has_signal = False
        try:
            while True:
                self._queue.get_nowait()
                has_signal = True
        except queue.Empty:
            pass
        if has_signal:
            self._reset_debounce_timer()

    def _reset_debounce_timer(self):
        if self._debounce_timer:
            self.root.after_cancel(self._debounce_timer)
        self._debounce_timer = self.root.after(80, self._evaluate)

    def _on_midi_event(self, hMidiIn, wMsg, dwInstance, dwParam1, dwParam2):
        if wMsg != 0x3C3:
            return
        status = dwParam1 & 0xFF
        if status == 0xFE:
            return

        note = (dwParam1 >> 8) & 0xFF
        velocity = (dwParam1 >> 16) & 0xFF

        if status & 0xF0 == 0x90 and velocity > 0:
            with self._lock:
                self._active_notes[note] = velocity
        elif status & 0xF0 == 0x80 or (status & 0xF0 == 0x90 and velocity == 0):
            with self._lock:
                self._active_notes.pop(note, None)
        else:
            return

        self._queue.put(True)

    def _evaluate(self):
        with self._lock:
            notes = list(self._active_notes.keys())
        chord = detect_chord(notes)
        self.callback(chord if chord else "")