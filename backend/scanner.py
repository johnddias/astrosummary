from __future__ import annotations
import os, re, sys
from datetime import datetime
from typing import Dict, Iterable, List, Tuple, Optional, Set
from astropy.io import fits
import unicodedata
import json
from pathlib import Path
import logging

logger = logging.getLogger("backend.scanner")

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
    print(f"DEBUG _iter_paths: root={root}, recurse={recurse}, exts={exts}", file=sys.stderr, flush=True)
    print(f"DEBUG _iter_paths: path exists: {os.path.exists(root)}, is_dir: {os.path.isdir(root)}", file=sys.stderr, flush=True)
    exts = {e.lower() for e in exts}
    file_count = 0
    if recurse:
        try:
            for dirpath, _, filenames in os.walk(root):
                print(f"DEBUG _iter_paths: walking {dirpath}, found {len(filenames)} files", file=sys.stderr, flush=True)
                for fn in filenames:
                    if os.path.splitext(fn)[1].lower() in exts:
                        file_count += 1
                        if file_count <= 3:
                            print(f"DEBUG _iter_paths: yielding file {file_count}: {os.path.join(dirpath, fn)}", file=sys.stderr, flush=True)
                        yield os.path.join(dirpath, fn)
        except Exception as e:
            print(f"DEBUG _iter_paths: ERROR in os.walk: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            raise
    else:
        try:
            files = os.listdir(root)
            print(f"DEBUG _iter_paths: listdir found {len(files)} items", file=sys.stderr, flush=True)
            for fn in files:
                p = os.path.join(root, fn)
                if os.path.isfile(p) and os.path.splitext(fn)[1].lower() in exts:
                    file_count += 1
                    if file_count <= 3:
                        print(f"DEBUG _iter_paths: yielding file {file_count}: {p}", file=sys.stderr, flush=True)
                    yield p
        except Exception as e:
            print(f"DEBUG _iter_paths: ERROR in listdir: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            raise
    print(f"DEBUG _iter_paths: total files found: {file_count}", file=sys.stderr, flush=True)

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

def _find_rejection_logs(root_path: str, recurse: bool) -> List[str]:
    """Find ProcessLogger.txt and similar rejection log files."""
    rejection_logs = []
    log_patterns = ["ProcessLogger.txt", "processlogger.txt", "*rejection*.txt", "*reject*.log"]
    
    if recurse:
        for dirpath, _, filenames in os.walk(root_path):
            for filename in filenames:
                if any(filename.lower() == pattern.lower() or 
                      ('*' in pattern and pattern.replace('*', '').lower() in filename.lower())
                      for pattern in log_patterns):
                    rejection_logs.append(os.path.join(dirpath, filename))
    else:
        for filename in os.listdir(root_path):
            filepath = os.path.join(root_path, filename)
            if os.path.isfile(filepath) and any(
                filename.lower() == pattern.lower() or 
                ('*' in pattern and pattern.replace('*', '').lower() in filename.lower())
                for pattern in log_patterns
            ):
                rejection_logs.append(filepath)
    
    return rejection_logs

def _is_frame_rejected(filename: str, rejected_filenames: Set[str]) -> bool:
    """
    Check if a frame is rejected, handling filename transformations.

    Handles cases where ProcessLogger contains calibrated names like 'file_c_lps.xisf'
    but the scan finds raw files like 'file.fit'.
    """
    if not rejected_filenames:
        return False

    # Direct match first
    if filename in rejected_filenames:
        logger.debug(f"Frame {filename} rejected via direct match")
        return True

    # Try matching without extension
    name_without_ext = Path(filename).stem
    for rejected_name in rejected_filenames:
        rejected_stem = Path(rejected_name).stem
        if name_without_ext == rejected_stem:
            logger.debug(f"Frame {filename} rejected via stem match with {rejected_name}")
            return True

    # Try matching with common calibration suffix patterns removed
    base_name = name_without_ext
    # Remove common suffixes that might be added during calibration
    calibration_suffixes = ['_c_lps', '_c', '_lps', '_cc', '_cal', '_calibrated']
    for suffix in calibration_suffixes:
        if base_name.endswith(suffix):
            base_name = base_name[:-len(suffix)]
            break

    # Also strip version numbers like _1, _2, _1_1, _1_2, etc. using regex
    import re
    base_name = re.sub(r'(_\d+)+$', '', base_name)

    # Check if any rejected file matches this base name
    for rejected_name in rejected_filenames:
        rejected_stem = Path(rejected_name).stem
        # Remove calibration suffixes from rejected names too
        rejected_base = rejected_stem
        for suffix in calibration_suffixes:
            if rejected_base.endswith(suffix):
                rejected_base = rejected_base[:-len(suffix)]
                break

        # Strip version numbers from rejected names too
        rejected_base = re.sub(r'(_\d+)+$', '', rejected_base)

        if base_name == rejected_base:
            logger.debug(f"Frame {filename} (base: {base_name}) rejected via suffix match with {rejected_name} (base: {rejected_base})")
            return True

    return False

def _parse_rejection_logs(log_paths: List[str]) -> Optional[Dict]:
    """Parse found rejection logs and return combined rejection data."""
    if not log_paths:
        return None

    try:
        # Try to import parser
        from rejection_log_parser import parse_rejection_log

        all_rejected_frames = set()
        all_quality_data = {}

        for log_path in log_paths:
            try:
                result = parse_rejection_log(log_path)
                all_rejected_frames.update(result.get('rejected_frames', []))
                all_quality_data.update(result.get('quality_data', {}))
            except Exception:
                continue  # Skip problematic logs

        if all_rejected_frames:
            logger.info(f"Parsed rejection logs: found {len(all_rejected_frames)} rejected frames")
            logger.info(f"Rejected filenames: {sorted(list(all_rejected_frames))[:10]}...")  # Show first 10
            return {
                'rejected_frames': list(all_rejected_frames),
                'quality_data': all_quality_data,
                'rejection_logs': log_paths,
                'rejected_count': len(all_rejected_frames)
            }
    except ImportError:
        pass  # Parser not available

    return None

def scan_directory(path: str, recurse: bool, extensions: List[str]):
    frames: List[Dict] = []
    files_scanned = 0
    files_matched = 0
    rejected_count = 0

    # Look for rejection logs
    rejection_logs = _find_rejection_logs(path, recurse)
    rejection_data = _parse_rejection_logs(rejection_logs)
    rejected_filenames = set(rejection_data.get('rejected_frames', [])) if rejection_data else set()

    # Debug logging - flush immediately
    print(f"DEBUG scan_directory: Starting scan of path: {path}", file=sys.stderr, flush=True)
    print(f"DEBUG scan_directory: Found {len(rejection_logs)} rejection logs", file=sys.stderr, flush=True)
    if rejection_data:
        print(f"DEBUG scan_directory: Parsed {len(rejected_filenames)} rejected frames", file=sys.stderr, flush=True)
        print(f"DEBUG scan_directory: Sample rejected files: {list(rejected_filenames)[:3]}", file=sys.stderr, flush=True)
    else:
        print("DEBUG scan_directory: No rejection data parsed", file=sys.stderr, flush=True)

    for fpath in _iter_paths(path, recurse, extensions):
        files_scanned += 1
        try:
            with fits.open(fpath, memmap=True) as hdul:
                hdr = hdul[0].header if len(hdul) else {}
                frame_type = _parse_type(hdr)
                if frame_type != "LIGHT":
                    if files_scanned <= 5:  # Log first few skipped files for debugging
                        print(f"DEBUG scan_directory: Skipping {Path(fpath).name} - frame_type={frame_type}, IMAGETYP={_get_first(hdr, TYPE_KEYS, 'NOT_FOUND')}", file=sys.stderr, flush=True)
                    continue

                # Check if this frame is rejected
                filename = Path(fpath).name
                is_rejected = _is_frame_rejected(filename, rejected_filenames)

                if is_rejected:
                    rejected_count += 1

                files_matched += 1
                target = _parse_target(hdr, fpath)
                filt   = _parse_filter(hdr, fpath)
                expo   = _parse_exposure(hdr)
                date   = _parse_date(hdr)

                frame_data = {
                    "target": target,
                    "filter": filt,
                    "exposure_s": float(expo),
                    "date": date,
                    "frameType": "LIGHT",
                    "file_path": fpath,
                }

                # Add rejection info if available
                if rejection_data:
                    frame_data["rejected"] = is_rejected

                frames.append(frame_data)
        except Exception as e:
            # Log errors for first few files to help debug
            if files_scanned <= 5:
                print(f"DEBUG scan_directory: Error reading {Path(fpath).name}: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            continue

    logger.info(f"Scan complete: {files_matched} light frames found, {rejected_count} marked as rejected (out of {len(rejected_filenames)} in rejection log)")

    result = frames, files_scanned, files_matched

    # Add rejection metadata if found
    if rejection_data:
        return result + (rejection_data,)

    return result


def stream_scan_directory(path: str, recurse: bool, extensions: List[str]):
    """Generator that yields newline-delimited JSON events while scanning.

    Events:
      { type: 'progress', files_scanned: int, files_matched: int }
      { type: 'frame', frame: { ... } }
      { type: 'done', files_scanned: int, files_matched: int, rejection_data?: {...} }
    """
    print(f"DEBUG stream_scan_directory: FUNCTION CALLED with path={path}", file=sys.stderr, flush=True)
    files_scanned = 0
    files_matched = 0
    rejected_count = 0

    # Look for rejection logs
    rejection_logs = _find_rejection_logs(path, recurse)
    rejection_data = _parse_rejection_logs(rejection_logs)
    rejected_filenames = set(rejection_data.get('rejected_frames', [])) if rejection_data else set()

    # Debug logging for stream scan - flush immediately
    print(f"DEBUG stream_scan: Starting scan of path: {path}", file=sys.stderr, flush=True)
    print(f"DEBUG stream_scan: Found {len(rejection_logs)} rejection logs", file=sys.stderr, flush=True)
    if rejection_data:
        print(f"DEBUG stream_scan: Parsed {len(rejected_filenames)} rejected frames", file=sys.stderr, flush=True)
        print(f"DEBUG stream_scan: Rejected filenames: {sorted(list(rejected_filenames))}", file=sys.stderr, flush=True)
    else:
        print("DEBUG stream_scan: No rejection data parsed", file=sys.stderr, flush=True)

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
                    if files_scanned <= 5:  # Log first few skipped files for debugging
                        print(f"DEBUG stream_scan: Skipping {Path(fpath).name} - frame_type={frame_type}, IMAGETYP={_get_first(hdr, TYPE_KEYS, 'NOT_FOUND')}", file=sys.stderr, flush=True)
                    continue

                # Check if this frame is rejected
                filename = Path(fpath).name
                is_rejected = _is_frame_rejected(filename, rejected_filenames)

                if is_rejected:
                    rejected_count += 1
                    print(f"DEBUG stream_scan: Frame {filename} marked as REJECTED", file=sys.stderr, flush=True)

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
                    'file_path': fpath,
                }

                # Add rejection info if available
                if rejection_data:
                    frame['rejected'] = is_rejected

                # include current counters and total_files so frontend can update progress together with the frame
                yield json.dumps({ 'type': 'frame', 'frame': frame, 'files_scanned': files_scanned, 'files_matched': files_matched, 'total_files': total_files }) + '\n'
        except Exception as e:
            # Log errors for first few files to help debug
            if files_scanned <= 5:
                print(f"DEBUG stream_scan: Error reading {Path(fpath).name}: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
            continue

    logger.info(f"Stream scan complete: {files_matched} light frames found, {rejected_count} marked as rejected (out of {len(rejected_filenames)} in rejection log)")
    print(f"DEBUG stream_scan: COMPLETE - {rejected_count} frames marked rejected out of {len(rejected_filenames)} in rejection log", file=sys.stderr, flush=True)

    # final summary (include rejection_data if found)
    done_event = { 'type': 'done', 'total_files': total_files, 'files_scanned': files_scanned, 'files_matched': files_matched }
    if rejection_data:
        done_event['rejection_data'] = rejection_data

    # Debug logging for done event
    print(f"DEBUG stream_scan done: rejection_data present: {rejection_data is not None}")
    if rejection_data:
        print(f"DEBUG stream_scan done: rejection_data keys: {list(rejection_data.keys())}")
    print(f"DEBUG stream_scan done: done_event keys: {list(done_event.keys())}")

    yield json.dumps(done_event) + '\n'
