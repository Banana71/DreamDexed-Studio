# harvester/ini_utils.py
import re

def hex_to_text(hex_string):
    try:
        bytes_list = hex_string.strip().split()
        if len(bytes_list) < 11:
            return "UNKNOWN"
        name_bytes = bytes_list[-11:-1]
        chars = [chr(int(b, 16)) for b in name_bytes]
        return "".join(chars).rstrip('\x00')
    except:
        return "ERROR"

def text_to_hex(text):
    text = text.ljust(10)[:10]
    hex_bytes = [f"{ord(char):02X}" for char in text]
    return " ".join(hex_bytes)

def parse_ini_for_voices(lines):
    tg_map = {i: {'hex': '', 'channel': 1, 'line_idx': -1, 'link': 0} for i in range(1, 9)}
    regex_link = re.compile(r"^TGLink(\d+)=(\d+)")
    regex_ch = re.compile(r"^MIDIChannel(\d+)=(\d+)")
    regex_voice = re.compile(r"^VoiceData(\d+)=(.*)")

    for idx, line in enumerate(lines):
        line = line.strip()
        m_link = regex_link.match(line)
        if m_link:
            tg = int(m_link.group(1))
            if 1 <= tg <= 8:
                tg_map[tg]['link'] = int(m_link.group(2))
        m_ch = regex_ch.match(line)
        if m_ch:
            tg = int(m_ch.group(1))
            if 1 <= tg <= 8:
                tg_map[tg]['channel'] = int(m_ch.group(2))
        m_voice = regex_voice.match(line)
        if m_voice:
            tg = int(m_voice.group(1))
            if 1 <= tg <= 8:
                tg_map[tg]['hex'] = m_voice.group(2)
                tg_map[tg]['line_idx'] = idx
    return tg_map

def rebuild_ini_line(original_line, new_hex):
    parts = original_line.strip().split('=')
    if len(parts) != 2:
        return original_line
    value_part = parts[1].strip().split()
    if len(value_part) < 11:
        return original_line
    new_value = " ".join(value_part[:-11]) + " " + new_hex + " " + value_part[-1]
    return f"{parts[0]}={new_value}\n"