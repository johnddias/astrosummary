from __future__ import annotations
import os, re
from datetime import datetime
from typing import Dict, Iterable, List, Tuple
from astropy.io import fits
import unicodedata
import json

CANON = {
    "ha": "Ha", "hα": "Ha", "h-a": "Ha", "halpha": "Ha",
    "oiii": "OIII", "o3": "OIII",
    "sii": "SII", "s2": "SII",
    "l": "L", "lum": "L", "luminance": "L",
    "r": "R", "red": "R",
    "g": "G", "green": "G",
    "b": "B", "blue": "B",
}

def _norm(s: str) -> str:
    if not s:
        return "Unknown"
    # strip, lowercase, remove spaces/underscores/dashes, fold accents
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode("ascii")
    t = t.strip().lower().replace(" ", "").replace("_", "").replace("-", "")
    return CANON.get(t, s.strip())

def _parse_filter(hdr, fallback_from_name: str) -> str:
    val = _get_first(hdr, FILT_KEYS)
    if val and str(val).strip():
        return _norm(str(val))

    # fallback from filename tokens
    base = os.path.basename(fallback_from_name)
    for token in ("ha", "oiii", "o3", "sii", "s2", "l", "lum", "r", "g", "b"):
        if re.search(rf"(?:^|[_\W]){token}(?:[_\W]|$)", base, flags=re.IGNORECASE):
            return _norm(token)

    return "Unknown"

DATE_KEYS = ("DATE-OBS", "DATEOBS", "DATE")
EXPO_KEYS = ("EXPTIME", "EXPOSURE")
FILT_KEYS = ("FILTER", "FILTER1", "FILTER2")
TYPE_KEYS = ("IMAGETYP", "IMAGETYP1", "FRAME")

def _iter_paths(root: str, recurse: bool, exts: List[str]) -> Iterable[str]:
    exts = {e.lower() for e in exts}
    if recurse:
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if os.path.splitext(fn)[1].lower() in exts:
                    yield os.path.join(dirpath, fn)
    else:
        for fn in os.listdir(root):
            p = os.path.join(root, fn)
            if os.path.isfile(p) and os.path.splitext(fn)[1].lower() in exts:
                yield p

def _get_first(hdr, keys: Tuple[str, ...], default=None):
    for k in keys:
        if k in hdr and hdr[k] not in (None, ""):
            return hdr[k]
    return default

def _parse_date(hdr) -> str:
    raw = _get_first(hdr, DATE_KEYS)
    if not raw:
        return datetime.utcnow().strftime("%Y-%m-%d")
    # astropy often stores ISO 8601; keep date part
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date().isoformat()
    except Exception:
        # try common formats
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(str(raw)[:19], fmt).date().isoformat()
            except Exception:
                pass
    return datetime.utcnow().strftime("%Y-%m-%d")

def _parse_exposure(hdr) -> float:
    val = _get_first(hdr, EXPO_KEYS, 0.0)
    try:
        return float(val)
    except Exception:
        return 0.0

def _parse_filter(hdr, fallback_from_name: str) -> str:
    val = _get_first(hdr, FILT_KEYS)
    if val and str(val).strip():
        return str(val).strip()
    # fallback from filename tokens: _Ha_, _OIII_, etc.
    base = os.path.basename(fallback_from_name).lower()
    for token in ("ha","oiii","sii","l","r","g","b"):
        if re.search(rf"(?:^|[_\W]){token}(?:[_\W]|$)", base):
            return {"ha":"Ha","oiii":"OIII","sii":"SII",
                    "l":"L","r":"R","g":"G","b":"B"}[token]
    return "Unknown"

def _parse_target(hdr, path: str) -> str:
    obj = hdr.get("OBJECT") or hdr.get("OBJCTRA")  # OBJECT is typical
    if obj and str(obj).strip():
        return str(obj).strip()
    # fallback to first token of filename
    name = os.path.basename(path)
    return re.split(r"[_.]", name, maxsplit=1)[0]

def _parse_type(hdr) -> str:
    val = _get_first(hdr, TYPE_KEYS, "")
    s = str(val).upper()
    if "LIGHT" in s: return "LIGHT"
    if "DARK"  in s: return "DARK"
    if "FLAT"  in s: return "FLAT"
    if "BIAS"  in s or "OFFSET" in s: return "BIAS"
    return "OTHER"

def scan_directory(path: str, recurse: bool, extensions: List[str]):
    frames: List[Dict] = []
    files_scanned = 0
    files_matched = 0

    for fpath in _iter_paths(path, recurse, extensions):
        files_scanned += 1
        try:
            with fits.open(fpath, memmap=True) as hdul:
                hdr = hdul[0].header if len(hdul) else {}
                frame_type = _parse_type(hdr)
                if frame_type != "LIGHT":
                    continue
                files_matched += 1
                target = _parse_target(hdr, fpath)
                filt   = _parse_filter(hdr, fpath)
                expo   = _parse_exposure(hdr)
                date   = _parse_date(hdr)

                frames.append({
                    "target": target,
                    "filter": filt,
                    "exposure_s": float(expo),
                    "date": date,
                    "frameType": "LIGHT",
                })
        except Exception:
            # Skip unreadable/corrupt files silently for MVP
            continue

    return frames, files_scanned, files_matched


def stream_scan_directory(path: str, recurse: bool, extensions: List[str]):
    """Generator that yields newline-delimited JSON events while scanning.

    Events:
      { type: 'progress', files_scanned: int, files_matched: int }
      { type: 'frame', frame: { ... } }
      { type: 'done', files_scanned: int, files_matched: int }
    """
    files_scanned = 0
    files_matched = 0

    # materialize the file list so the frontend can show a total file count up front
    paths = list(_iter_paths(path, recurse, extensions))
    total_files = len(paths)

    # initial progress with total_files set (0 scanned yet)
    yield json.dumps({ 'type': 'progress', 'total_files': total_files, 'files_scanned': 0, 'files_matched': 0 }) + '\n'

    for fpath in paths:
        files_scanned += 1
        # emit progress update for UI (include total_files)
        yield json.dumps({ 'type': 'progress', 'total_files': total_files, 'files_scanned': files_scanned, 'files_matched': files_matched }) + '\n'
        try:
            with fits.open(fpath, memmap=True) as hdul:
                hdr = hdul[0].header if len(hdul) else {}
                frame_type = _parse_type(hdr)
                if frame_type != 'LIGHT':
                    continue
                files_matched += 1
                target = _parse_target(hdr, fpath)
                filt   = _parse_filter(hdr, fpath)
                expo   = _parse_exposure(hdr)
                date   = _parse_date(hdr)

                frame = {
                    'target': target,
                    'filter': filt,
                    'exposure_s': float(expo),
                    'date': date,
                    'frameType': 'LIGHT',
                }
                # include current counters and total_files so frontend can update progress together with the frame
                yield json.dumps({ 'type': 'frame', 'frame': frame, 'files_scanned': files_scanned, 'files_matched': files_matched, 'total_files': total_files }) + '\n'
        except Exception:
            # skip silently
            continue

    # final summary (include total_files for completeness)
    yield json.dumps({ 'type': 'done', 'total_files': total_files, 'files_scanned': files_scanned, 'files_matched': files_matched }) + '\n'
