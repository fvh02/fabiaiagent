"""3D-Druck add-on: find models on Printables, slice them for the Bambu Lab P1S and print them.

Small JSON API on the internal Home Assistant network, used by the `druck` command of the
Inkbox Claude Gateway. It is not exposed on the home network.
"""

import asyncio
import io
import json
import logging
import os
import re
import secrets
import shutil
import time
import zipfile
from pathlib import Path

import aiohttp
from aiohttp import web

import printables
import slicer
from printer import Printer, PrinterError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("druck3d")

DATA = Path(os.environ.get("DRUCK_DATA", "/data"))
JOBS = DATA / "jobs"
PORT = int(os.environ.get("DRUCK_PORT", "8095"))
MAX_DOWNLOAD = 250 * 1024 * 1024
MAX_FILES = 12
MODEL_EXT = (".stl", ".3mf", ".obj", ".step", ".stp")
JOB_TTL = 14 * 86400
SUPERVISOR = os.environ.get("SUPERVISOR_URL", "http://supervisor")
INKBOX = os.environ.get("INKBOX_IMESSAGE_URL", "https://inkbox.ai/api/v1/imessage")


def load_options() -> dict:
    try:
        return json.loads((DATA / "options.json").read_text())
    except (OSError, ValueError):
        return {}


OPT = load_options()
PRINTER = Printer(OPT.get("printer_ip") or "", OPT.get("printer_serial") or "", OPT.get("access_code") or "",
                  int(os.environ.get("DRUCK_MQTT_PORT", "8883")), int(os.environ.get("DRUCK_FTP_PORT", "990")))
WATCH_EVERY = float(os.environ.get("DRUCK_WATCH_INTERVAL", "60"))
MATERIAL = OPT.get("material") or "PLA"
PLATE = OPT.get("plate") or "Textured PEI Plate"
USE_AMS = bool(OPT.get("use_ams"))
AMS_SLOT = int(OPT.get("ams_slot") or 1)
CAMERA = (OPT.get("camera_entity") or "").strip()
INKBOX_KEY = (OPT.get("inkbox_api_key") or "").strip()
NOTIFY_TO = (OPT.get("imessage_to") or "").strip()

routes = web.RouteTableDef()


def fail(message: str, status: int = 400):
    """Stop the request with a JSON error the gateway can pass on."""
    cls = web.HTTPBadRequest if status == 400 else web.HTTPServiceUnavailable
    raise cls(text=json.dumps({"error": message}, ensure_ascii=False), content_type="application/json")


def safe_name(text: str) -> str:
    text = re.sub(r"[^A-Za-z0-9äöüÄÖÜß _-]+", "", text).strip().replace(" ", "_")
    return text[:48] or "modell"


# -- jobs ------------------------------------------------------------------------
def job_dir(job_id: str) -> Path:
    if not re.fullmatch(r"[a-z0-9]{8}", job_id or ""):
        fail("Unbekannter Auftrag")
    path = JOBS / job_id
    if not path.exists():
        fail("Unbekannter Auftrag – bitte neu vorbereiten")
    return path


def save_job(job: dict) -> None:
    (JOBS / job["id"] / "job.json").write_text(json.dumps(job, ensure_ascii=False, indent=1))


def load_job(job_id: str) -> dict:
    return json.loads((job_dir(job_id) / "job.json").read_text())


def cleanup_jobs() -> None:
    if not JOBS.exists():
        return
    for path in JOBS.iterdir():
        if path.is_dir() and time.time() - path.stat().st_mtime > JOB_TTL:
            shutil.rmtree(path, ignore_errors=True)


async def fetch(session: aiohttp.ClientSession, url: str, dest: Path) -> Path:
    async with session.get(url, timeout=aiohttp.ClientTimeout(total=600), headers={"User-Agent": printables.HEADERS["User-Agent"]}) as resp:
        if resp.status >= 400:
            fail(f"Download fehlgeschlagen ({resp.status})")
        size = 0
        with dest.open("wb") as fh:
            async for chunk in resp.content.iter_chunked(1 << 16):
                size += len(chunk)
                if size > MAX_DOWNLOAD:
                    fail("Die Datei ist zu groß")
                fh.write(chunk)
    return dest


def unpack(path: Path, folder: Path) -> list[Path]:
    """Model files from a download: the file itself or the model files inside a zip."""
    if path.suffix.lower() in MODEL_EXT:
        return [path]
    if zipfile.is_zipfile(path) and path.suffix.lower() != ".3mf":
        out = []
        with zipfile.ZipFile(path) as z:
            for info in z.infolist():
                name = Path(info.filename).name
                if info.is_dir() or not name.lower().endswith(MODEL_EXT) or name.startswith("."):
                    continue
                if info.file_size > MAX_DOWNLOAD:
                    continue
                target = folder / safe_name(Path(name).stem)
                target = target.with_suffix(Path(name).suffix.lower())
                with z.open(info) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                out.append(target)
        return out
    return []


# -- API ---------------------------------------------------------------------------
@routes.get("/api/ping")
async def api_ping(_: web.Request) -> web.Response:
    return web.json_response({"ok": True, "printer": PRINTER.configured, "imessage": bool(INKBOX_KEY and NOTIFY_TO)})


@routes.get("/api/search")
async def api_search(request: web.Request) -> web.Response:
    query = request.query.get("q", "").strip()
    if not query:
        fail("Bitte einen Suchbegriff angeben")
    limit = max(1, min(10, int(request.query.get("limit", "5"))))
    try:
        results = await printables.search(request.app["http"], query, limit)
    except (printables.PrintablesError, aiohttp.ClientError, asyncio.TimeoutError) as err:
        fail(str(err), 503)
    sent = 0
    if request.query.get("send") == "1":
        for n, r in enumerate(results, 1):
            image = await download_image(request.app["http"], r.get("image"))
            if await notify(request.app["http"], f"{n}) {r['name']} · ❤ {r.get('likes') or 0}", image):
                sent += 1
    return web.json_response({"query": query, "results": results, "images_sent": sent})


async def download_image(session: aiohttp.ClientSession, url: str | None) -> bytes | None:
    if not url or not url.startswith(printables.MEDIA):
        return None
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status == 200 and int(resp.headers.get("Content-Length") or 0) < 9_000_000:
                return await resp.read()
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    return None


@routes.post("/api/send")
async def api_send(request: web.Request) -> web.Response:
    """Send a picture to the owner by iMessage: the printer camera or a model image from Printables."""
    body = await request.json()
    if not (INKBOX_KEY and NOTIFY_TO):
        fail("iMessage ist im 3D-Druck-Add-on nicht eingerichtet (Inkbox-API-Key und Handynummer)")
    session = request.app["http"]
    image = await camera_image(session) if body.get("camera") else await download_image(session, body.get("image_url"))
    if not image:
        fail("Kein Bild gefunden", 503)
    if not await notify(session, str(body.get("text") or "")[:300], image):
        fail("Senden fehlgeschlagen", 503)
    return web.json_response({"sent": True})


@routes.post("/api/prepare")
async def api_prepare(request: web.Request) -> web.Response:
    body = await request.json()
    source = str(body.get("model") or "").strip()
    if not source:
        fail("Bitte ein Modell angeben (Printables-ID oder Link)")
    wanted = [str(w).lower() for w in body.get("files") or []]
    material = str(body.get("material") or MATERIAL).upper()
    quality = str(body.get("quality") or "standard").lower()
    session = request.app["http"]
    job_id = secrets.token_hex(4)
    folder = JOBS / job_id
    (folder / "models").mkdir(parents=True)
    job = {"id": job_id, "source": source, "created": time.time(), "material": material, "quality": quality}
    try:
        mid = printables.model_id(source)
        models: list[Path] = []
        available: list[str] = []
        if mid:
            info = await printables.files(session, mid)
            job.update(name=info["name"], url=info["url"], image=info["image"])
            stls = info["stls"]
            available = [f["name"] for f in stls]
            if wanted:
                stls = [f for f in stls if any(w in f["name"].lower() for w in wanted)]
            if not stls:
                fail("Keine passenden Modelldateien gefunden. Verfügbar: " + ", ".join(available[:20]))
            if len(stls) > MAX_FILES:
                fail(f"Das Modell hat {len(stls)} Dateien – bitte mit --datei auswählen. Verfügbar: " + ", ".join(available[:30]))
            for f in stls:
                link = await printables.download_link(session, mid, f["id"])
                ext = Path(f["name"]).suffix.lower() or ".stl"
                dest = folder / "models" / (safe_name(Path(f["name"]).stem) + ext)
                await fetch(session, link, dest)
                models += unpack(dest, folder / "models")
        elif source.startswith(("https://", "http://")):
            name = Path(source.split("?")[0]).name or "modell.stl"
            dest = folder / "models" / (safe_name(Path(name).stem) + (Path(name).suffix.lower() or ".stl"))
            await fetch(session, source, dest)
            models = unpack(dest, folder / "models")
            job.update(name=Path(name).stem, url=source)
            if wanted:
                models = [m for m in models if any(w in m.name.lower() for w in wanted)]
        else:
            fail("Bitte eine Printables-ID, einen Printables-Link oder einen Link zu einer STL/3MF-Datei angeben")
        if not models:
            fail("In diesem Download ist keine druckbare Datei (STL, 3MF, OBJ, STEP)")
        if len(models) > MAX_FILES:
            fail(f"{len(models)} Dateien sind zu viele für eine Platte – bitte mit --datei auswählen: "
                 + ", ".join(m.name for m in models[:30]))
        job["files"] = [m.name for m in models]
        info = await asyncio.to_thread(
            slicer.slice_models, models, folder, safe_name(job.get("name") or "modell"), material, quality,
            bool(body.get("supports")), bool(body.get("orient")), str(body.get("plate") or PLATE))
        job.update(info)
        if info.get("outside"):
            job["warning"] = "Nicht alles passt auf die Druckplatte – bitte weniger Teile wählen (--datei)."
        save_job(job)
    except web.HTTPException:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    except (printables.PrintablesError, slicer.SliceError, aiohttp.ClientError, asyncio.TimeoutError, OSError) as err:
        shutil.rmtree(folder, ignore_errors=True)
        fail(str(err) or err.__class__.__name__, 503)
    return web.json_response(public(job))


def public(job: dict) -> dict:
    out = {k: v for k, v in job.items() if k != "file"}
    if job.get("seconds"):
        h, m = divmod(round(job["seconds"] / 60), 60)
        out["time"] = f"{h} h {m} min" if h else f"{m} min"
    return out


@routes.get("/api/jobs/{job_id}")
async def api_job(request: web.Request) -> web.Response:
    return web.json_response(public(load_job(request.match_info["job_id"])))


@routes.post("/api/print")
async def api_print(request: web.Request) -> web.Response:
    body = await request.json()
    job = load_job(str(body.get("job") or ""))
    if job.get("warning"):
        fail(job["warning"])
    try:
        status = await asyncio.to_thread(PRINTER.refresh)
        if status["raw_state"] in ("RUNNING", "PREPARE", "PAUSE"):
            fail(f"Der Drucker ist beschäftigt ({status['state']}, {status.get('job') or 'unbekannter Auftrag'})")
        remote = await asyncio.to_thread(PRINTER.start, Path(job["file"]), job.get("name") or "Druck",
                                         USE_AMS, AMS_SLOT)
    except PrinterError as err:
        fail(str(err), 503)
    job["started"] = time.time()
    job["remote"] = remote
    save_job(job)
    task = asyncio.create_task(watch(job))
    watchers.add(task)
    task.add_done_callback(watchers.discard)
    return web.json_response({"started": job.get("name"), "time": public(job).get("time"), "weight_g": job.get("weight_g")})


@routes.get("/api/status")
async def api_status(request: web.Request) -> web.Response:
    try:
        return web.json_response(await asyncio.to_thread(PRINTER.refresh))
    except PrinterError as err:
        fail(str(err), 503)


@routes.post("/api/control")
async def api_control(request: web.Request) -> web.Response:
    body = await request.json()
    cmd = {"pause": "pause", "pausieren": "pause", "weiter": "resume", "resume": "resume",
           "stop": "stop", "stopp": "stop", "abbrechen": "stop"}.get(str(body.get("cmd")).lower())
    if not cmd:
        fail("Unbekannter Befehl (pause, weiter, stopp)")
    try:
        await asyncio.to_thread(PRINTER.command, cmd)
        await asyncio.sleep(2)
        return web.json_response({"done": cmd, "status": await asyncio.to_thread(PRINTER.refresh)})
    except PrinterError as err:
        fail(str(err), 503)


async def camera_image(session: aiohttp.ClientSession) -> bytes:
    token = os.environ.get("SUPERVISOR_TOKEN", "")
    if not token:
        fail("Kein Zugriff auf Home Assistant", 503)
    headers = {"Authorization": f"Bearer {token}"}
    entity = CAMERA
    if not entity:
        async with session.get(f"{SUPERVISOR}/core/api/states", headers=headers) as resp:
            states = await resp.json(content_type=None) if resp.status == 200 else []
        cams = [s for s in states if str(s.get("entity_id", "")).startswith("camera.")]
        def score(s):
            text = (s["entity_id"] + " " + str((s.get("attributes") or {}).get("friendly_name", ""))).lower()
            return ("p1s" in text) * 4 + ("bambu" in text) * 2 + ("druck" in text or "print" in text) + ("kamera" in text or "camera" in text)
        cams = sorted((c for c in cams if score(c) >= 2), key=score, reverse=True)
        if not cams:
            fail("Keine Druckerkamera in Home Assistant gefunden (Bambu-Lab-Integration). Kamera im Add-on eintragen.", 503)
        entity = cams[0]["entity_id"]
    async with session.get(f"{SUPERVISOR}/core/api/camera_proxy/{entity}", headers=headers,
                           timeout=aiohttp.ClientTimeout(total=30)) as resp:
        if resp.status != 200:
            fail(f"Kamerabild nicht verfügbar ({entity}, {resp.status}) – ist die Kamera in der Bambu-Integration an?", 503)
        return await resp.read()


@routes.get("/api/camera")
async def api_camera(request: web.Request) -> web.Response:
    return web.Response(body=await camera_image(request.app["http"]), content_type="image/jpeg")


# -- notifications ----------------------------------------------------------------
async def notify(session: aiohttp.ClientSession, text: str, image: bytes | None = None) -> bool:
    if not (INKBOX_KEY and NOTIFY_TO):
        return False
    headers = {"X-API-Key": INKBOX_KEY}
    try:
        body = {"to": NOTIFY_TO, "text": text}
        if image:
            form = aiohttp.FormData()
            form.add_field("file", io.BytesIO(image), filename="drucker.jpg", content_type="image/jpeg")
            async with session.post(f"{INKBOX}/media", data=form, headers=headers) as resp:
                if resp.status < 300:
                    body["media_urls"] = [(await resp.json(content_type=None))["media_url"]]
        async with session.post(f"{INKBOX}/messages", json=body, headers=headers) as resp:
            if resp.status >= 300:
                log.warning("iMessage fehlgeschlagen: %s %s", resp.status, (await resp.text())[:200])
                return False
            return True
    except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, ValueError) as err:
        log.warning("iMessage fehlgeschlagen: %s", err)
        return False


async def watch(job: dict) -> None:
    """Follow a print the assistant started and report when it is done."""
    session = app_ref["http"]
    seen_running = False
    started = time.time()
    while time.time() - started < 3 * 86400:
        await asyncio.sleep(WATCH_EVERY)
        try:
            status = await asyncio.to_thread(PRINTER.refresh)
        except PrinterError as err:
            log.info("Status nicht abrufbar: %s", err)
            continue
        raw = status["raw_state"]
        if raw in ("RUNNING", "PREPARE", "PAUSE"):
            seen_running = True
            continue
        if raw in ("FINISH", "FAILED") or (seen_running and raw == "IDLE"):
            image = None
            try:
                image = await camera_image(session)
            except web.HTTPException:
                pass
            name = job.get("name") or "Dein Druck"
            text = f"✅ {name} ist fertig gedruckt." if raw == "FINISH" else f"⚠️ {name}: Druck abgebrochen oder fehlgeschlagen ({status['state']})."
            await notify(session, text, image)
            return


app_ref: dict = {}
watchers: set[asyncio.Task] = set()


async def on_startup(app: web.Application) -> None:
    JOBS.mkdir(parents=True, exist_ok=True)
    cleanup_jobs()
    app["http"] = aiohttp.ClientSession()
    app_ref["http"] = app["http"]
    log.info("3D-Druck bereit auf Port %s – Drucker %s, %s, Platte %s%s", PORT,
             PRINTER.host or "(nicht eingerichtet)", MATERIAL, PLATE, ", AMS" if USE_AMS else "")


async def on_cleanup(app: web.Application) -> None:
    await app["http"].close()
    PRINTER.close()


def main() -> None:
    app = web.Application(client_max_size=1024 * 1024)
    app.add_routes(routes)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    web.run_app(app, host=None, port=PORT, print=None, access_log=None)


if __name__ == "__main__":
    main()
