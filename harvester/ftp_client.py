# harvester/ftp_client.py
import ftplib
from typing import Optional, Callable, Any

class FTPClient:
    def __init__(self, host: str, user: str, password: str, timeout: int = 15):
        self.host = host
        self.user = user
        self.password = password
        self.timeout = timeout
        self.ftp: Optional[ftplib.FTP] = None

    def connect(self) -> ftplib.FTP:
        """Stellt Verbindung her und gibt das FTP-Objekt zurück."""
        self.ftp = ftplib.FTP(self.host, timeout=self.timeout)
        self.ftp.login(self.user, self.password)
        return self.ftp

    def close(self):
        if self.ftp:
            try:
                self.ftp.close()
            except:
                pass
            self.ftp = None

    def execute(self, operation: Callable[[ftplib.FTP], Any], log_func: Optional[Callable] = None) -> Any:
        """Führt eine Operation aus und behandelt Verbindungsauf- und -abbau."""
        try:
            self.connect()
            return operation(self.ftp)
        except Exception as e:
            if log_func:
                log_func(f"FTP-Error: {str(e)}")
            raise
        finally:
            self.close()