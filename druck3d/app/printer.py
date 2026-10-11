"""Talk to a Bambu Lab printer in LAN mode: upload files over FTPS, send commands over MQTT.

Needs the printer's IP address, serial number and LAN access code (printer screen: Settings →
Network). Since 2025 the printer only accepts third-party print commands in LAN-only mode with
"Developer mode" switched on.
"""

import ftplib
import hashlib
import json
import logging
import socket
import ssl
import threading
import time
import uuid
from pathlib import Path

import paho.mqtt.client as mqtt

log = logging.getLogger("printer")

STATES = {
    "IDLE": "bereit", "PREPARE": "bereitet vor", "RUNNING": "druckt", "PAUSE": "pausiert",
    "FINISH": "fertig", "FAILED": "fehlgeschlagen", "SLICING": "slict", "INIT": "startet",
}


class PrinterError(Exception):
    pass


def _tls() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # the printer uses a self-signed certificate
    return ctx


class ImplicitFTPS(ftplib.FTP_TLS):
    """FTPS with implicit TLS (port 990) and TLS session reuse, as the Bambu printers require."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, context=_tls(), **kwargs)
        self._sock = None

    @property
    def sock(self):
        return self._sock

    @sock.setter
    def sock(self, value):
        if value is not None and not isinstance(value, ssl.SSLSocket):
            value = self.context.wrap_socket(value)
        self._sock = value

    def ntransfercmd(self, cmd, rest=None):
        conn, size = ftplib.FTP.ntransfercmd(self, cmd, rest)
        if self._prot_p:
            conn = self.context.wrap_socket(conn, server_hostname=self.host, session=self.sock.session)
        return conn, size


class Printer:
    def __init__(self, host: str, serial: str, access_code: str, port_mqtt: int = 8883, port_ftp: int = 990):
        self.host, self.serial, self.code = host.strip(), serial.strip(), access_code.strip()
        self.port_mqtt, self.port_ftp = port_mqtt, port_ftp
        self.state: dict = {}
        self.updated = 0.0
        self._client: mqtt.Client | None = None
        self._lock = threading.Lock()
        self._connected = threading.Event()
        self._fresh = threading.Event()

    @property
    def configured(self) -> bool:
        return bool(self.host and self.serial and self.code)

    # -- MQTT ------------------------------------------------------------------
    def _connect(self) -> mqtt.Client:
        with self._lock:
            if self._client and self._connected.is_set():
                return self._client
            if not self.configured:
                raise PrinterError("Der Drucker ist nicht eingerichtet (IP, Seriennummer und Zugangscode im Add-on).")
            client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"druck3d-{uuid.uuid4().hex[:8]}")
            client.username_pw_set("bblp", self.code)
            client.tls_set_context(_tls())
            client.tls_insecure_set(True)
            client.on_connect = self._on_connect
            client.on_disconnect = self._on_disconnect
            client.on_message = self._on_message
            self._connected.clear()
            try:
                client.connect(self.host, self.port_mqtt, keepalive=30)
            except (OSError, ssl.SSLError) as err:
                raise PrinterError(f"Drucker nicht erreichbar ({self.host}): {err}") from err
            client.loop_start()
            if not self._connected.wait(10):
                client.loop_stop()
                raise PrinterError("Keine Verbindung zum Drucker – ist der LAN-Modus an und der Zugangscode richtig?")
            self._client = client
            return client

    def _on_connect(self, client, userdata, flags, reason, properties=None):
        if reason == 0 or getattr(reason, "value", 1) == 0:
            client.subscribe(f"device/{self.serial}/report")
            self._connected.set()
        else:
            log.warning("MQTT-Verbindung abgelehnt: %s", reason)

    def _on_disconnect(self, client, userdata, *args):
        self._connected.clear()

    def _on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload)
        except ValueError:
            return
        report = data.get("print")
        if isinstance(report, dict):
            # The P1 series sends only what changed; keep the full picture.
            self.state.update(report)
            self.updated = time.time()
            self._fresh.set()

    def _publish(self, payload: dict) -> None:
        client = self._connect()
        info = client.publish(f"device/{self.serial}/request", json.dumps(payload), qos=1)
        info.wait_for_publish(10)

    def refresh(self, wait: float = 6) -> dict:
        self._fresh.clear()
        self._publish({"pushing": {"sequence_id": "0", "command": "pushall", "version": 1, "push_target": 1}})
        self._fresh.wait(wait)
        if not self.state:
            raise PrinterError("Der Drucker antwortet nicht")
        return self.status()

    def status(self) -> dict:
        s = self.state
        raw = s.get("gcode_state") or "?"
        return {
            "state": STATES.get(raw, raw.lower()), "raw_state": raw,
            "percent": s.get("mc_percent"), "remaining_min": s.get("mc_remaining_time"),
            "layer": s.get("layer_num"), "layers": s.get("total_layer_num"),
            "job": s.get("subtask_name") or None,
            "nozzle_c": s.get("nozzle_temper"), "bed_c": s.get("bed_temper"),
            "error": s.get("print_error") or 0,
        }

    def command(self, name: str) -> None:
        if name not in ("pause", "resume", "stop"):
            raise PrinterError("Unbekannter Befehl")
        self._publish({"print": {"sequence_id": "0", "command": name, "param": ""}})

    def close(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None

    # -- printing -----------------------------------------------------------------
    def upload(self, file: Path, remote_name: str) -> None:
        if not self.configured:
            raise PrinterError("Der Drucker ist nicht eingerichtet (IP, Seriennummer und Zugangscode im Add-on).")
        try:
            ftp = ImplicitFTPS()
            ftp.connect(self.host, self.port_ftp, timeout=30)
            ftp.login("bblp", self.code)
            ftp.prot_p()
            with file.open("rb") as fh:
                ftp.storbinary(f"STOR {remote_name}", fh)
            try:
                ftp.quit()
            except (OSError, EOFError, ftplib.Error):
                pass  # some firmware closes the control connection right away
        except (OSError, EOFError, ftplib.Error, ssl.SSLError, socket.timeout) as err:
            raise PrinterError(f"Hochladen zum Drucker fehlgeschlagen: {err}") from err

    def start(self, file: Path, title: str, use_ams: bool = False, ams_slot: int = 1,
              bed_levelling: bool = True, timelapse: bool = False) -> str:
        plain = file.name.translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}))
        remote = "".join(ch if ch.isascii() and (ch.isalnum() or ch in "-_.") else "_" for ch in plain)
        self.upload(file, remote)
        import zipfile
        with zipfile.ZipFile(file) as z:
            gcode_md5 = hashlib.md5(z.read("Metadata/plate_1.gcode")).hexdigest()
        self._publish({"print": {
            "sequence_id": "0", "command": "project_file", "param": "Metadata/plate_1.gcode",
            "url": f"file:///sdcard/{remote}", "md5": gcode_md5, "subtask_name": title[:60],
            "project_id": "0", "profile_id": "0", "task_id": "0", "subtask_id": "0",
            "timelapse": timelapse, "bed_type": "auto", "bed_levelling": bed_levelling, "bed_leveling": bed_levelling,
            "flow_cali": False, "vibration_cali": False, "layer_inspect": False,
            "use_ams": use_ams, "ams_mapping": [max(0, ams_slot - 1)] if use_ams else [],
        }})
        return remote
