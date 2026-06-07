# harvester/ftp_utils.py
import ftplib
from typing import Optional, Callable, Any

def safe_ftp_operation(creds, operation_func, log_func=None):
    """
    Führt eine FTP-Operation sicher aus.
    creds: Dictionary mit 'ip', 'user', 'password' oder None.
    """
    if not creds or not isinstance(creds, dict) or "ip" not in creds:
        if log_func:
            log_func("FTP-Fehler: Keine gültigen Verbindungsdaten.")
        return None
    ftp = None
    try:
        ftp = ftplib.FTP(creds["ip"], timeout=15)
        ftp.login(creds["user"], creds["password"])
        return operation_func(ftp)
    except Exception as e:
        if log_func:
            log_func(f"FTP-Fehler: {str(e)}")
        raise
    finally:
        if ftp:
            try:
                ftp.close()
            except:
                pass