"""Slice models for the Bambu Lab P1S with the OrcaSlicer command line.

OrcaSlicer's CLI only accepts complete ("flattened") presets, so the system presets that inherit
from each other are merged here first. The P1S profile lists two nozzle variants (standard and
high flow); the CLI crashes on that, so only the standard nozzle is kept.
"""

import json
import logging
import os
import subprocess
import zipfile
from pathlib import Path

log = logging.getLogger("slicer")

ORCA = Path(os.environ.get("ORCA_DIR", "/opt/orca"))
PROFILES = ORCA / "resources" / "profiles" / "BBL"
PRINTER = os.environ.get("DRUCK_PRINTER_PRESET", "Bambu Lab P1S 0.4 nozzle")
SLICE_TIMEOUT = 900


class SliceError(Exception):
    pass


def _index() -> dict:
    index = {}
    for kind in ("machine", "process", "filament"):
        for file in (PROFILES / kind).rglob("*.json"):
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and "name" in data:
                index[(kind, data["name"])] = data
    return index


_INDEX: dict | None = None


def index() -> dict:
    global _INDEX
    if _INDEX is None:
        _INDEX = _index()
    return _INDEX


def flatten(kind: str, name: str) -> dict:
    data = index()[(kind, name)]
    parent = data.get("inherits")
    merged = flatten(kind, parent) if parent and (kind, parent) in index() else {}
    merged = dict(merged)
    merged.update(data)
    merged.pop("inherits", None)
    return merged


def _compatible(data: dict) -> bool:
    printers = data.get("compatible_printers") or []
    return PRINTER in printers


def choose_process(quality: str = "standard") -> str:
    layer = {"fein": "0.12mm", "standard": "0.20mm", "schnell": "0.28mm"}.get(quality, "0.20mm")
    candidates = [name for (kind, name), data in index().items()
                  if kind == "process" and name.startswith(layer) and _compatible(flatten(kind, name))]
    if not candidates:
        raise SliceError(f"Kein Druckprofil {layer} für {PRINTER} gefunden")
    # Prefer the plain "Standard"/"Fine"/... preset over "Strength", "Quality" etc.
    candidates.sort(key=lambda n: (not any(w in n for w in ("Standard", "Fine", "Draft", "Optimal", "Extra Draft")), len(n)))
    return candidates[0]


def choose_filament(material: str = "PLA") -> str:
    material = material.upper()
    found = []
    for (kind, name), data in index().items():
        if kind != "filament" or data.get("instantiation") == "false":
            continue
        flat = flatten(kind, name)
        types = flat.get("filament_type") or []
        if _compatible(flat) and (types[0] if isinstance(types, list) and types else types) == material:
            found.append(name)
    if not found:
        raise SliceError(f"Kein Filamentprofil für {material} gefunden")
    found.sort(key=lambda n: (not n.startswith(f"Bambu {material} Basic"), not n.startswith(f"Generic {material}"), len(n)))
    return found[0]


def write_presets(folder: Path, material: str, quality: str, supports: bool, plate: str) -> tuple[Path, Path, Path, dict]:
    machine = flatten("machine", PRINTER)
    # Keep only the standard nozzle (see module docstring).
    machine["extruder_variant_list"] = ["Direct Drive Standard"]
    machine["nozzle_volume_type"] = ["Standard"]
    machine["printer_settings_id"] = machine["name"]
    process_name, filament_name = choose_process(quality), choose_filament(material)
    process = flatten("process", process_name)
    process["print_settings_id"] = process["name"]
    process["curr_bed_type"] = plate
    if supports:
        process["enable_support"] = "1"
        process["support_type"] = "tree(auto)"
    filament = flatten("filament", filament_name)
    filament["filament_settings_id"] = [filament["name"]]
    paths = []
    for data, file in ((machine, "machine.json"), (process, "process.json"), (filament, "filament.json")):
        data["from"] = "system"
        path = folder / file
        path.write_text(json.dumps(data), encoding="utf-8")
        paths.append(path)
    return paths[0], paths[1], paths[2], {"process": process_name, "filament": filament_name}


def slice_models(models: list[Path], folder: Path, name: str, material: str = "PLA",
                 quality: str = "standard", supports: bool = False, orient: bool = False,
                 plate: str = "Textured PEI Plate") -> dict:
    """Slice the given STL/3MF/OBJ files onto one plate. Returns time, weight and the output file."""
    machine, process, filament, chosen = write_presets(folder, material, quality, supports, plate)
    out = folder / "out"
    out.mkdir(exist_ok=True)
    target = f"{name}.gcode.3mf"
    cmd = [str(ORCA / "AppRun"), "--debug", "1", "--slice", "0", "--arrange", "1",
           "--orient", "1" if orient else "0",
           "--load-settings", f"{machine};{process}", "--load-filaments", str(filament),
           "--outputdir", str(out), "--export-3mf", target, *map(str, models)]
    log.info("Slicen: %s", " ".join(cmd))
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=SLICE_TIMEOUT,
                              env={**os.environ, "HOME": str(folder), "LC_ALL": "C"})
    except subprocess.TimeoutExpired as err:
        raise SliceError("Das Slicen hat zu lange gedauert") from err
    result = {}
    try:
        result = json.loads((out / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    file = out / target
    if proc.returncode != 0 or not file.exists():
        message = result.get("error_string") or (proc.stderr or proc.stdout or "").strip()[-400:] or f"Fehlercode {proc.returncode}"
        raise SliceError(f"Slicen fehlgeschlagen: {message}")
    info = read_info(file)
    info.update(chosen, file=str(file))
    return info


def read_info(file: Path) -> dict:
    info = {"seconds": None, "weight_g": None, "plates": 0, "outside": False, "supports": False}
    with zipfile.ZipFile(file) as z:
        names = z.namelist()
        info["plates"] = sum(1 for n in names if n.startswith("Metadata/plate_") and n.endswith(".gcode"))
        try:
            text = z.read("Metadata/slice_info.config").decode("utf-8", "replace")
        except KeyError:
            return info
    import re
    m = re.search(r'key="prediction" value="(\d+)"', text)
    info["seconds"] = int(m.group(1)) if m else None
    m = re.search(r'key="weight" value="([\d.]+)"', text)
    info["weight_g"] = float(m.group(1)) if m else None
    info["outside"] = 'key="outside" value="true"' in text
    info["supports"] = 'key="support_used" value="true"' in text
    return info
