import csv
import re
import threading
from queue import Queue
from pathlib import Path
from datetime import datetime
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import Dict, Tuple, Optional, Any

import PySimpleGUI as sg
from astropy.io import fits

# ---------------- Theme compatibility (new vs old PySimpleGUI) ----------------
def set_theme(name: str = "DarkBlue3"):
    if hasattr(sg, "theme"):
        sg.theme(name)  # newer API
    else:
        sg.change_look_and_feel(name)  # older API

# ---------------- Defaults / Config ----------------
DEFAULT_OUTPUT = "astrobin_acquisitions.csv"
DEFAULT_FILTER_MAP_TEXT = (
    "R=3007\n"
    "Ha=4657\n"
    "OIII=4746\n"
    "SII=4838\n"
    "L=3012\n"
    "G=3011\n"
    "B=3008\n"
)

# Ratio schemas (edit as desired)
GOAL_RATIOS = {
    "SHO (2:1:1)": {"Ha": 2, "OIII": 1, "SII": 1},
    "HOO (2:1)": {"Ha": 2, "OIII": 1},
    "LRGB (2:1:1:1)": {"L": 2, "R": 1, "G": 1, "B": 1},
}
DEFAULT_SCHEMA_NAME = "SHO (2:1:1)"

# Filter aliases for ratio planner normalization
ALIASES = {
    "ha": "Ha", "hα": "Ha", "halpha": "Ha",
    "oiii": "OIII", "o3": "OIII",
    "sii": "SII", "s2": "SII",
    "luminance": "L", "lum": "L",
    "red": "R", "green": "G", "blue": "B",
}

# ---------------- Helpers: mapping, optional FITS fields ----------------
def parse_filter_map(text: str) -> Dict[str, int]:
    mapping: Dict[str, int] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, val = line.split("=", 1)
        name, val = name.strip(), val.strip()
        if not name:
            continue
        try:
            mapping[name] = int(val)
        except ValueError:
            continue
    return mapping

def val_or_blank(values_set: set) -> str:
    cleaned = {v for v in values_set if v not in (None, "", "Unknown")}
    if len(cleaned) == 1:
        return str(next(iter(cleaned)))
    return ""

def read_iso(hdr) -> Optional[int]:
    for k in ("ISO", "ISOSPEED", "PHOTOMET", "ISOSET"):
        if k in hdr:
            try:
                return int(hdr.get(k))
            except Exception:
                try:
                    return int(float(hdr.get(k)))
                except Exception:
                    pass
    return None

def read_binning(hdr) -> Optional[int]:
    for k in ("XBINNING", "BINNING", "XBIN"):
        if k in hdr:
            try:
                return int(hdr.get(k))
            except Exception:
                try:
                    return int(float(hdr.get(k)))
                except Exception:
                    pass
    if "BINNING" in hdr:
        val = str(hdr.get("BINNING"))
        if "x" in val.lower():
            try:
                return int(val.lower().split("x")[0])
            except Exception:
                pass
    return None

def read_gain(hdr) -> Optional[float]:
    for k in ("GAIN", "GAINSETTING", "GAIN_SET"):
        if k in hdr:
            try:
                return float(hdr.get(k))
            except Exception:
                pass
    return None

# ---------------- Extraction for AstroBin import (date, filter, exp, optional fields) ----------------
def extract_fits_metadata(path: Path) -> Optional[Tuple[str, str, float, Optional[int], Optional[int], Optional[float]]]:
    try:
        with fits.open(path, ignore_missing_end=True, memmap=True) as hdul:
            hdr = hdul[0].header
            date_obs = hdr.get("DATE-OBS")
            filt = hdr.get("FILTER", "Unknown")
            exptime_raw = hdr.get("EXPTIME", 0)
            if not date_obs:
                return None
            date_token = str(date_obs).split("T")[0].strip()
            date_str = datetime.fromisoformat(date_token).strftime("%Y-%m-%d")
            exptime = float(exptime_raw)
            iso = read_iso(hdr)
            binning = read_binning(hdr)
            gain = read_gain(hdr)
            return (date_str, str(filt), exptime, iso, binning, gain)
    except Exception:
        return None

def summarize_metadata(files, progress_q: Queue = None):
    """
    Group by date -> filter -> exposure time.
    Track per-group sets for optional fields.
    """
    summary: Dict[str, Dict[str, Dict[float, Dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(lambda: {
            "count": 0,
            "iso_set": set(),
            "binning_set": set(),
            "gain_set": set(),
        }))
    )
    with ProcessPoolExecutor() as executor:
        futures = {executor.submit(extract_fits_metadata, f): f for f in files}
        for i, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            if res:
                date, filt, exptime, iso, binning, gain = res
                bucket = summary[date][filt][exptime]
                bucket["count"] += 1
                bucket["iso_set"].add(iso if iso is not None else "")
                bucket["binning_set"].add(binning if binning is not None else "")
                bucket["gain_set"].add(gain if gain is not None else "")
            if progress_q:
                progress_q.put(("tick", i))
    return summary

def build_csv_text(summary, filter_map: Dict[str, int], include_iso: bool, include_binning: bool, include_gain: bool) -> str:
    fieldnames = ["date", "filter", "number", "duration"]
    if include_iso:
        fieldnames.append("iso")
    if include_binning:
        fieldnames.append("binning")
    if include_gain:
        fieldnames.append("gain")

    from io import StringIO
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()

    for date, filt_dict in summary.items():
        for filt, exp_dict in filt_dict.items():
            for exptime, stats in exp_dict.items():
                row = {
                    "date": date,
                    "filter": filter_map.get(filt, ""),
                    "number": stats["count"],
                    "duration": round(float(exptime), 4),
                }
                if include_iso:
                    row["iso"] = val_or_blank(stats["iso_set"])
                if include_binning:
                    row["binning"] = val_or_blank(stats["binning_set"])
                if include_gain:
                    g = val_or_blank(stats["gain_set"])
                    try:
                        row["gain"] = f"{float(g):.2f}" if g != "" else ""
                    except Exception:
                        row["gain"] = ""
                writer.writerow(row)

    return buf.getvalue()

def write_text(path: Path, text: str):
    path.write_text(text, encoding="utf-8")

# ---------------- Ratio planner ----------------
def norm_filter(name: str) -> str:
    if not name:
        return "Unknown"
    k = str(name).strip().lower()
    return ALIASES.get(k, name.strip())

def extract_target_filter_exptime(fpath: Path):
    try:
        with fits.open(fpath, ignore_missing_end=True, memmap=True) as hdul:
            hdr = hdul[0].header
            target = (hdr.get("OBJECT") or "").strip() or "(Unknown Target)"
            filt = norm_filter(hdr.get("FILTER", "Unknown"))
            exptime = float(hdr.get("EXPTIME", 0))
            if exptime <= 0:
                return None
            return (target, filt, exptime)
    except Exception:
        return None

def scan_fits_for_target_totals(files):
    totals = defaultdict(lambda: defaultdict(float))  # totals[target][filter] = seconds
    with ProcessPoolExecutor() as pool:
        futures = {pool.submit(extract_target_filter_exptime, f): f for f in files}
        for fut in as_completed(futures):
            res = fut.result()
            if res:
                target, filt, exptime = res
                totals[target][filt] += exptime
    return totals

def normalize_ratio(d: dict):
    total = sum(d.values()) or 1.0
    return {k: v/total for k, v in d.items()}

def balance_deficits(current_s: dict, goal_ratio: dict):
    """Keep the strongest feasible scale (no reductions)."""
    if not current_s:
        return {}, {}
    goal_keys = list(goal_ratio.keys())
    current = {k: current_s.get(k, 0.0) for k in goal_keys}
    if all(v == 0 for v in current.values()):
        return {k: 0.0 for k in goal_keys}, {k: 0.0 for k in goal_keys}
    bases = []
    for k in goal_keys:
        g = goal_ratio[k]
        if g > 0:
            bases.append(current[k] / g if current[k] > 0 else 0.0)
    base = min(bases) if bases else 0.0
    desired = {k: goal_ratio[k]*base for k in goal_keys}
    deficits = {k: max(0.0, desired[k] - current[k]) for k in goal_keys}
    return desired, deficits

def plan_to_total_hours(current_s: dict, goal_ratio: dict, total_hours: float):
    total_seconds = total_hours * 3600.0
    sum_goal = sum(goal_ratio.values()) or 1.0
    desired = {k: total_seconds * (goal_ratio[k] / sum_goal) for k in goal_ratio.keys()}
    deficits = {k: max(0.0, desired[k] - current_s.get(k, 0.0)) for k in desired.keys()}
    return desired, deficits

def human_time(seconds: float) -> str:
    h = seconds / 3600.0
    if h >= 1.0:
        return f"{h:.2f} h"
    m = seconds / 60.0
    return f"{m:.0f} m"

def build_target_ratio_report(totals_by_target: dict, schema_name: str, desired_total_hours: Optional[float]):
    goal = GOAL_RATIOS[schema_name]
    lines = []
    for target, filt_secs in sorted(totals_by_target.items()):
        have = {f: filt_secs.get(f, 0.0) for f in sorted(filt_secs.keys())}
        have_ratio = normalize_ratio({k: v for k, v in have.items() if v > 0})
        desired_bal, deficits_bal = balance_deficits(filt_secs, goal)
        desired_tot, deficits_tot = ({}, {})
        if desired_total_hours and desired_total_hours > 0:
            desired_tot, deficits_tot = plan_to_total_hours(filt_secs, goal, desired_total_hours)

        lines.append(f"Target: {target}")
        lines.append("  Current totals:")
        for f in sorted(have.keys()):
            lines.append(f"    {f:<4} {human_time(have[f]):>8}")
        if have_ratio:
            rtxt = "  Current ratios: " + ", ".join(f"{k}={have_ratio[k]:.2f}" for k in sorted(have_ratio.keys()))
            lines.append(rtxt)
        gtxt = "  Goal ratios:    " + ", ".join(f"{k}={goal[k]}" for k in goal.keys())
        lines.append(gtxt)
        if desired_bal:
            lines.append("  Balance-to-goal (keep strongest fixed):")
            for f in goal.keys():
                want = desired_bal.get(f, 0.0)
                need = deficits_bal.get(f, 0.0)
                lines.append(f"    {f:<4} want {human_time(want):>8}  need {human_time(need):>8}")
        if desired_total_hours and desired_tot:
            lines.append(f"  Plan to {desired_total_hours:.1f} h total:")
            for f in goal.keys():
                want = desired_tot.get(f, 0.0)
                need = deficits_tot.get(f, 0.0)
                lines.append(f"    {f:<4} want {human_time(want):>8}  need {human_time(need):>8}")
        lines.append("")
    return "\n".join(lines)

# ---------------- Workers ----------------
def astobin_worker(folder: Path, recurse: bool, filter_map_text: str,
                   add_iso: bool, add_binning: bool, add_gain: bool,
                   out_csv: Path, progress_q: Queue):
    try:
        exts = ("*.fits", "*.fit")
        files = [f for ext in exts for f in (folder.rglob(ext) if recurse else folder.glob(ext))]
        total = len(files)
        progress_q.put(("total", total))
        if total == 0:
            progress_q.put(("done", "No FITS files found."))
            return
        filter_map = parse_filter_map(filter_map_text)
        summary = summarize_metadata(files, progress_q)
        csv_text = build_csv_text(summary, filter_map, add_iso, add_binning, add_gain)
        write_text(out_csv, csv_text)
        progress_q.put(("preview", csv_text))
        progress_q.put(("done", f"AstroBin CSV saved to: {out_csv}"))
    except Exception as e:
        progress_q.put(("done", f"Error: {e}"))

def ratio_worker(folder: Path, recurse: bool, schema_name: str, desired_hours: Optional[float], progress_q: Queue):
    try:
        exts = ("*.fits", "*.fit")
        files = [f for ext in exts for f in (folder.rglob(ext) if recurse else folder.glob(ext))]
        total = len(files)
        progress_q.put(("rtotal", total))
        if total == 0:
            progress_q.put(("rdone", "No FITS files found."))
            return
        # Progress for ratio: we don’t tick per file to keep it simple; scanning uses a pool internally.
        totals = scan_fits_for_target_totals(files)
        report = build_target_ratio_report(totals, schema_name, desired_hours)
        progress_q.put(("rpreview", report))
        progress_q.put(("rdone", "Ratio report ready."))
    except Exception as e:
        progress_q.put(("rdone", f"Error: {e}"))

# ---------------- GUI ----------------
def main():
    set_theme("DarkBlue3")

    # Global controls
    top_controls = [
        [sg.Text("Image folder"), sg.Input(key="-FOLDER-", expand_x=True), sg.FolderBrowse()],
        [sg.Checkbox("Recurse subfolders", key="-RECURSE-", default=True)],
    ]

    # Tab 1: AstroBin Import
    tab_ast = [
        [sg.Text("Output CSV"), sg.Input(DEFAULT_OUTPUT, key="-CSV-", expand_x=True),
         sg.FileSaveAs(file_types=(("CSV", "*.csv"),))],
        [sg.Frame("Optional AstroBin Fields", [
            [sg.Checkbox("ISO", key="-ADD_ISO-", default=False),
             sg.Checkbox("Binning", key="-ADD_BINNING-", default=False),
             sg.Checkbox("Gain", key="-ADD_GAIN-", default=False)]
        ])],
        [sg.Frame("Filter → AstroBin ID map (edit lines like 'Ha=4657')", [
            [sg.Multiline(DEFAULT_FILTER_MAP_TEXT, key="-MAPTEXT-", size=(44, 9))]
        ])],
        [sg.Button("Start AstroBin Export", key="-START_AST-"), sg.Push(), sg.Text("", key="-STATUS-", size=(60,1))],
        [sg.ProgressBar(100, orientation="h", size=(45, 20), key="-PROG-")],
        [sg.Text("CSV Preview (full) — ready to paste into AstroBin")],
        [sg.Multiline(size=(100, 18), key="-PREVIEW-", autoscroll=True, disabled=True)],
        [sg.Button("Copy CSV to Clipboard", key="-COPYCSV-")],
    ]

    # Tab 2: Ratio Planner
    tab_ratio = [
        [sg.Text("Goal schema"),
         sg.Combo(list(GOAL_RATIOS.keys()), default_value=DEFAULT_SCHEMA_NAME, key="-SCHEMA-", readonly=True),
         sg.Text("Desired total hours (optional)"),
         sg.Input("", key="-DESHOURS-", size=(10,1))],
        [sg.Button("Generate Ratio Report", key="-START_RATIO-"), sg.Push(), sg.Text("", key="-RSTATUS-", size=(60,1))],
        [sg.ProgressBar(100, orientation="h", size=(45, 20), key="-RPROG-")],
        [sg.Text("Ratio Report")],
        [sg.Multiline(size=(100, 24), key="-RPREV-", autoscroll=True, disabled=True)],
        [sg.Button("Copy Report to Clipboard", key="-COPYREP-")],
    ]

    layout = top_controls + [[sg.TabGroup([[sg.Tab("AstroBin Import", tab_ast), sg.Tab("Ratio Planner", tab_ratio)]])]]

    window = sg.Window("AstroSummary GUI", layout, finalize=True, resizable=True)
    progress_q = Queue()
    total = processed = 0
    rtotal = rprocessed = 0  # reserved (we keep ratio progress simple)

    while True:
        event, values = window.read(timeout=100)

        if event in (sg.WIN_CLOSED, "Cancel"):
            break

        # Start AstroBin export
        if event == "-START_AST-":
            folder = Path(values.get("-FOLDER-") or "")
            if not folder.exists():
                window["-STATUS-"].update("Select a valid folder.")
                continue
            recurse = bool(values.get("-RECURSE-", True))
            out_csv = Path(values.get("-CSV-") or DEFAULT_OUTPUT)
            map_text = values.get("-MAPTEXT-", DEFAULT_FILTER_MAP_TEXT)
            add_iso = bool(values.get("-ADD_ISO-", False))
            add_binning = bool(values.get("-ADD_BINNING-", False))
            add_gain = bool(values.get("-ADD_GAIN-", False))

            window["-STATUS-"].update("Starting…")
            window["-PREVIEW-"].update("")
            window["-PROG-"].update(0)
            processed = total = 0

            threading.Thread(
                target=astobin_worker,
                args=(folder, recurse, map_text, add_iso, add_binning, add_gain, out_csv, progress_q),
                daemon=True
            ).start()

        # Start Ratio report
        if event == "-START_RATIO-":
            folder = Path(values.get("-FOLDER-") or "")
            if not folder.exists():
                window["-RSTATUS-"].update("Select a valid folder.")
                continue
            recurse = bool(values.get("-RECURSE-", True))
            schema_name = values.get("-SCHEMA-", DEFAULT_SCHEMA_NAME)
            des_hours_raw = values.get("-DESHOURS-", "").strip()
            des_hours = None
            if des_hours_raw:
                try:
                    des_hours = float(des_hours_raw)
                    if des_hours <= 0:
                        des_hours = None
                except Exception:
                    des_hours = None

            window["-RSTATUS-"].update("Starting…")
            window["-RPREV-"].update("")
            window["-RPROG-"].update(0)

            threading.Thread(
                target=ratio_worker,
                args=(folder, recurse, schema_name, des_hours, progress_q),
                daemon=True
            ).start()

        # Copy CSV
        if event == "-COPYCSV-":
            text = window["-PREVIEW-"].get()
            if hasattr(sg, "clipboard_set"):
                sg.clipboard_set(text)
            else:
                try:
                    window.TKroot.clipboard_clear()
                    window.TKroot.clipboard_append(text)
                except Exception:
                    pass
            window["-STATUS-"].update("CSV copied to clipboard.")

        # Copy Ratio report
        if event == "-COPYREP-":
            text = window["-RPREV-"].get()
            if hasattr(sg, "clipboard_set"):
                sg.clipboard_set(text)
            else:
                try:
                    window.TKroot.clipboard_clear()
                    window.TKroot.clipboard_append(text)
                except Exception:
                    pass
            window["-RSTATUS-"].update("Report copied to clipboard.")

        # Pump progress queue
        try:
            while True:
                kind, payload = progress_q.get_nowait()
                # AstroBin progress
                if kind == "total":
                    total = payload
                    window["-STATUS-"].update(f"Found {total} files.")
                elif kind == "tick":
                    processed = payload
                    pct = int((processed / max(total, 1)) * 100)
                    window["-PROG-"].update(pct)
                    if processed % 50 == 0 or processed == total:
                        window["-STATUS-"].update(f"Processed {processed}/{total}")
                elif kind == "preview":
                    window["-PREVIEW-"].update(payload)
                elif kind == "done":
                    window["-STATUS-"].update(str(payload))

                # Ratio progress
                elif kind == "rtotal":
                    rtotal = payload
                    window["-RSTATUS-"].update(f"Found {rtotal} files.")
                    window["-RPROG-"].update(100 if rtotal == 0 else 25)
                elif kind == "rpreview":
                    window["-RPREV-"].update(payload)
                    window["-RPROG-"].update(75)
                elif kind == "rdone":
                    window["-RSTATUS-"].update(str(payload))
                    window["-RPROG-"].update(100)
        except Exception:
            pass

    window.close()

if __name__ == "__main__":
    main()
